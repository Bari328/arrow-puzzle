# -*- coding: utf-8 -*-
"""基于帧计数的动画状态：被撞箭头的左右晃动。

需求要求"不使用 time.sleep、基于帧计数实现动画"，所以这里用主循环的帧号驱动：
    ShakeAnimation.cell         晃动的箭头坐标 (row, col)
    ShakeAnimation.start_frame  动画起始帧（主循环跑到第几帧时触发的）
绘制时用 (当前帧 - 起始帧) 推算偏移量，动画播完偏移自然回到 0，
整个过程只改数据、不做等待，因此不会阻塞主循环。
"""

import math

from .config import SHAKE_AMPLITUDE, SHAKE_CYCLES, SHAKE_FRAMES


class ShakeAnimation:
    """一次"被撞停"的左右晃动动画。"""

    def __init__(self, cell, start_frame, frames=SHAKE_FRAMES,
                 amplitude=SHAKE_AMPLITUDE, cycles=SHAKE_CYCLES):
        self.cell = cell                  # 晃动的箭头坐标
        self.start_frame = start_frame    # 动画起始帧
        self.frames = max(int(frames), 1)  # 动画总帧数
        self.amplitude = amplitude
        self.cycles = cycles

    def elapsed_frames(self, frame):
        """到当前帧为止，动画已经播放了多少帧。"""
        return max(frame - self.start_frame, 0)

    def progress(self, frame):
        """播放进度，取值 0.0 ~ 1.0。"""
        return min(self.elapsed_frames(frame) / self.frames, 1.0)

    def finished(self, frame):
        """动画是否已经播完。"""
        return self.elapsed_frames(frame) >= self.frames

    def offset(self, frame):
        """当前帧应叠加的偏移量：只有横向分量，所以表现为"左右晃动"。"""
        progress = self.progress(frame)
        if progress >= 1.0:
            return (0.0, 0.0)
        decay = 1.0 - progress                          # 幅度随时间衰减，看起来更自然
        wave = math.sin(progress * math.tau * self.cycles)
        return (wave * self.amplitude * decay, 0.0)


class ShakeManager:
    """管理当前正在进行的所有晃动动画。"""

    def __init__(self):
        self.animations = []

    def start(self, cell, start_frame):
        """让某个格子的箭头开始晃动；同一格重复触发时重新计时。"""
        self.animations = [item for item in self.animations if item.cell != cell]
        animation = ShakeAnimation(cell, start_frame)
        self.animations.append(animation)
        return animation

    def offset(self, cell, frame):
        """某格在当前帧应有的偏移（绘制函数里调用）。"""
        dx = dy = 0.0
        for animation in self.animations:
            if animation.cell == cell:
                offset_x, offset_y = animation.offset(frame)
                dx += offset_x
                dy += offset_y
        return (dx, dy)

    def update(self, frame):
        """按当前帧号清理已经播完的动画。"""
        self.animations = [item for item in self.animations if not item.finished(frame)]

    def is_active(self):
        """是否还有晃动动画在播。"""
        return bool(self.animations)

    def active_cells(self):
        """正在晃动的格子坐标列表。"""
        return [item.cell for item in self.animations]

    def clear(self):
        """清空所有晃动动画（切关 / 重开时调用）。"""
        self.animations.clear()
