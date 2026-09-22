# -*- coding: utf-8 -*-
"""音效模块：所有音效都由代码合成波形，不加载任何外部音频文件。

用法：
    1) 在 pygame.init() 之前调用 Audio.prepare()，先把混音器参数定好；
    2) pygame.init() 之后创建 Audio()，它会合成好全部音效；
    3) 用 audio.play("shoot") 之类的方式播放，静音 / 无音频设备时静默跳过。

音效波形都是"频率曲线 + 起音衰减包络"简单合成，用标准库 array 打包成
16bit 缓冲，直接交给 pygame.mixer.Sound(buffer=...)。

不同的机器音频设备格式不一样（本机实测是 8 声道），所以这里会按
pygame.mixer.get_init() 返回的实际采样率与声道数来合成，保证音高和时长不走样。
"""

import array
import math
import random

import pygame

from .config import (
    AUDIO_ENABLED,
    AUDIO_MASTER_VOLUME,
    AUDIO_SAMPLE_RATE,
    AUDIO_VOLUMES,
)

# 优先申请的混音格式：44100Hz、16bit 有符号、双声道（实际以设备返回为准）
PREFERRED_MIXER = (AUDIO_SAMPLE_RATE, -16, 2)


def _wave(kind, phase):
    """基础波形：正弦 / 三角 / 方波 / 锯齿。"""
    sine = math.sin(phase)
    if kind == "square":
        return 1.0 if sine >= 0 else -1.0
    if kind == "triangle":
        return (2.0 / math.pi) * math.asin(sine)
    if kind == "saw":
        return 2.0 * (phase / math.tau - math.floor(phase / math.tau + 0.5))
    return sine


def _envelope(t, attack=0.006, decay=16.0):
    """起音 + 指数衰减包络，让每个音有"啪"的一下起音和自然的尾巴。"""
    if t < attack:
        return t / attack
    return math.exp(-decay * (t - attack))


def _join(*chunks):
    """把若干段音首尾拼接（用来做琶音与音阶）。"""
    return b"".join(chunks)


class Audio:
    """音效管理器：合成、播放与静音控制。"""

    def __init__(self, enabled=AUDIO_ENABLED, rng=None):
        self.enabled = enabled
        self.muted = False
        self.sounds = {}
        self.rng = rng or random.Random(2026)
        self.sample_rate = AUDIO_SAMPLE_RATE
        self.channels = 2
        self.ready = self._ensure_mixer()
        if self.ready and self.enabled:
            self._build_sounds()

    # ------------------------------------------------------------------
    # 初始化
    # ------------------------------------------------------------------
    @staticmethod
    def prepare():
        """在 pygame.init() 之前调用，先申请一个合适的混音格式。"""
        try:
            pygame.mixer.pre_init(AUDIO_SAMPLE_RATE, -16, 2, 512)
        except pygame.error:
            pass

    def _ensure_mixer(self):
        """确认混音器可用；不可用则返回 False（游戏照常运行，只是没声音）。

        对设备格式持宽容态度：只要拿到采样率/声道数就按它合成，
        只有拿不到 16bit 有符号格式时才放弃音效。
        """
        mixer = pygame.mixer.get_init()
        if mixer is not None and mixer[1] != -16:
            # 只支持 16bit 有符号；先按偏好格式重开一次试试
            try:
                pygame.mixer.quit()
                pygame.mixer.init(*PREFERRED_MIXER, 512)
            except pygame.error:
                return False
            mixer = pygame.mixer.get_init()
        if mixer is None or mixer[1] != -16:
            return False
        self.sample_rate = mixer[0]
        self.channels = mixer[2]
        return True

    # ------------------------------------------------------------------
    # 波形合成
    # ------------------------------------------------------------------
    def _synth(self, duration, freq_fn, wave="sine", volume=0.8,
               attack=0.006, decay=16.0, noise=0.0):
        """合成一段音，返回可直接交给 Sound 的 16bit 字节流。

        freq_fn 接收 0.0~1.0 的播放进度，返回该时刻的频率，用来做滑音。
        采样率与声道数取自当前音频设备，因此时长和音高都是准确的。
        """
        frames = max(int(self.sample_rate * duration), 1)
        dt = 1.0 / self.sample_rate
        buffer = array.array("h")
        phase = 0.0
        for index in range(frames):
            t = index * dt
            freq = max(freq_fn(index / frames), 20.0)
            phase += math.tau * freq * dt
            value = _wave(wave, phase) * _envelope(t, attack, decay)
            if noise:
                value = (1.0 - noise) * value + noise * (self.rng.random() * 2.0 - 1.0)
            sample = int(max(-1.0, min(1.0, value * volume)) * 32767)
            for _ in range(self.channels):    # 每个声道写同样的采样
                buffer.append(sample)
        return buffer.tobytes()

    def _build_sounds(self):
        """一次性合成所有音效。"""
        builders = {
            "shoot": self._make_shoot,     # 箭头飞出：向上的"咻"
            "block": self._make_block,     # 撞到阻挡：低沉的"咚"
            "clear": self._make_clear,     # 通关：上行琶音
            "fail": self._make_fail,       # 失败：下行音阶
            "click": self._make_click,     # 按钮点击
            "hover": self._make_hover,     # 鼠标划过
            "start": self._make_start,     # 进入关卡：两音上行
        }
        for name, builder in builders.items():
            volume = AUDIO_MASTER_VOLUME * AUDIO_VOLUMES.get(name, 1.0)
            try:
                sound = pygame.mixer.Sound(buffer=builder())
            except (pygame.error, ValueError):
                continue               # 单个音效合成失败不影响其它音效
            sound.set_volume(max(0.0, min(volume, 1.0)))
            self.sounds[name] = sound

    # ------------------------------------------------------------------
    # 播放与开关
    # ------------------------------------------------------------------
    def play(self, name):
        """播放指定音效；未就绪 / 已静音时静默跳过，返回播放通道或 None。"""
        if not (self.enabled and self.ready) or self.muted:
            return None
        sound = self.sounds.get(name)
        if sound is None:
            return None
        try:
            return sound.play()
        except pygame.error:
            return None

    def toggle(self):
        """开关音效，返回切换后是否发声。"""
        self.muted = not self.muted
        return self.on

    @property
    def on(self):
        """当前是否处于"能听到声音"的状态。"""
        return bool(self.enabled and self.ready and not self.muted)

    def status_text(self):
        """给界面显示用的状态文字。"""
        if not self.ready:
            return "音效：不可用"
        return "音效：开 (M)" if self.on else "音效：关 (M)"

    # ------------------------------------------------------------------
    # 各个音效的合成配方
    # ------------------------------------------------------------------
    def _make_shoot(self):
        """箭头飞出：频率快速上滑 + 一点噪声，像"咻"地飞走。"""
        return self._synth(0.18, lambda p: 700.0 + 1500.0 * p, "sine",
                           volume=0.85, attack=0.004, decay=17.0, noise=0.16)

    def _make_block(self):
        """撞到阻挡：低频三角波 + 噪声做成"咚"的撞击感。"""
        return self._synth(0.24, lambda p: 200.0 - 70.0 * p, "triangle",
                           volume=0.9, attack=0.002, decay=13.0, noise=0.22)

    def _make_clear(self):
        """通关：C-E-G-C 上行琶音。"""
        notes = (523.25, 659.25, 783.99, 1046.50)
        return _join(*[self._synth(0.13, lambda p, f=freq: f * (1.0 + 0.01 * p),
                                   "triangle", volume=0.8, decay=11.0)
                       for freq in notes])

    def _make_fail(self):
        """失败：三个下行音，略带方波的钝感。"""
        notes = (392.00, 311.13, 233.08)
        return _join(*[self._synth(0.20, lambda p, f=freq: f * (0.98 + 0.02 * p),
                                   "square", volume=0.45, decay=8.0)
                       for freq in notes])

    def _make_click(self):
        """按钮点击：很短的清脆音。"""
        return self._synth(0.05, lambda p: 1000.0, "sine",
                           volume=0.7, attack=0.002, decay=42.0)

    def _make_hover(self):
        """鼠标划过：更短更轻的一声。"""
        return self._synth(0.035, lambda p: 1500.0, "sine",
                           volume=0.5, attack=0.002, decay=50.0)

    def _make_start(self):
        """进入关卡：两音上行。"""
        return _join(
            self._synth(0.11, lambda p: 659.25, "triangle", volume=0.75, decay=12.0),
            self._synth(0.15, lambda p: 987.77, "triangle", volume=0.75, decay=10.0),
        )
