# -*- coding: utf-8 -*-
"""游戏主程序：状态机 + 主循环。

四个界面（开始 / 游戏 / 通关 / 失败）在这里按状态分发事件、更新与绘制；
棋盘逻辑、关卡生成、特效与画面分别交给 board / levels / effects / renderer。
碰撞晃动动画由 animation.ShakeManager 基于帧计数驱动，失误次数由 self.mistakes_left 统一维护。
"""

import random

import pygame

from . import renderer
from .animation import ShakeManager
from .audio import Audio
from .config import (
    ARROW_COLORS,
    AUTO_NEXT_DELAY,
    BOTTOM_BUTTON_TOP,
    COLOR_DANGER,
    COLOR_SUCCESS,
    COLOR_TEXT_DIM,
    DIRECTION_VECTORS,
    FPS,
    MAX_DT,
    SCORE_PER_ARROW,
    SCORE_PER_MISTAKE,
    SHAKE_DURATION,
    WINDOW_HEIGHT,
    WINDOW_TITLE,
    WINDOW_WIDTH,
)
from .effects import Effects
from .levels import generate_level
from .menu_scene import MenuScene
from .ui import Button


class App:
    """游戏应用：持有窗口、字体、棋盘与所有界面状态。"""

    STATE_MENU = "menu"      # 开始界面
    STATE_PLAY = "play"      # 游戏界面
    STATE_CLEAR = "clear"    # 通关界面
    STATE_OVER = "over"      # 失败界面

    def __init__(self, seed=None):
        Audio.prepare()                # 混音参数必须在 pygame.init() 之前设好
        pygame.init()
        pygame.display.set_caption(WINDOW_TITLE)
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()
        self.fonts = renderer.Fonts()
        self.background = renderer.make_background()
        self.rng = random.Random(seed)
        self.effects = Effects()
        self.shake = ShakeManager()    # 基于帧计数的晃动动画管理器
        self.frame_count = 0           # 主循环帧号，动画用它推算偏移
        self.audio = Audio(rng=random.Random(seed))   # 音效全部由代码合成
        self.menu_scene = MenuScene(self.rng)         # 开始界面的动态画面

        # ---- 整体状态 ----
        self.running = True
        self.state = self.STATE_MENU
        self.level_index = 1           # 当前（或下一个要挑战的）关卡
        self.best_level = 0            # 已通关的最高关卡
        self.total_score = 0           # 累计得分
        self.show_hint = True          # 是否显示悬停辅助线

        # ---- 当前关卡状态 ----
        self.board = None
        self.layout = None
        self.initial_grid = None       # 出题时的棋盘，用于"重新开始本关"
        self.arrow_total = 0
        self.mistakes_total = 0        # 本关初始失误次数（每关 3 次）
        self.mistakes_left = 0         # 剩余失误次数，扣到 0 即失败
        self.score = 0
        self.hover_cell = None
        self.auto_next_timer = 0.0     # 通关后自动进入下一关的倒计时
        self.fail_pending = False      # 失误已归零，等晃动动画播完就切失败界面

        self._build_buttons()

    # ------------------------------------------------------------------
    # 按钮
    # ------------------------------------------------------------------
    def _build_buttons(self):
        """一次性创建四个界面的按钮，之后复用。"""
        center_x = WINDOW_WIDTH // 2
        button_w, button_h = renderer.MENU_BUTTON_SIZE
        gap = renderer.MENU_BUTTON_GAP
        row_y = renderer.MENU_BUTTON_ROW_Y
        total = button_w * 3 + gap * 2
        start_x = (WINDOW_WIDTH - total) // 2
        self.menu_buttons = [
            Button((start_x, row_y, button_w, button_h),
                   "▶ 开始游戏", self.button_action(self.start_new_game),
                   base_color=(56, 92, 72), hover_color=(78, 132, 100)),
            Button((start_x + button_w + gap, row_y, button_w, button_h),
                   "继续第 1 关", self.button_action(self.continue_game)),
            Button((start_x + 2 * (button_w + gap), row_y, button_w, button_h),
                   "退出游戏", self.button_action(self.quit_game)),
            Button(renderer.MENU_SOUND_CHIP, "音效：开 (M)",
                   self.button_action(self.toggle_sound), font_size=19),
        ]
        self.play_buttons = [
            Button((92, BOTTOM_BUTTON_TOP, 200, 48), "重新开始 (R)",
                   self.button_action(self.restart_level), font_size=22),
            Button((WINDOW_WIDTH - 92 - 200, BOTTOM_BUTTON_TOP, 200, 48),
                   "返回主菜单 (ESC)", self.button_action(self.back_to_menu), font_size=22),
        ]
        self.clear_buttons = [
            Button((center_x - 170, 452, 340, button_h), "进入下一关 (空格)",
                   self.button_action(self.next_level),
                   base_color=(48, 92, 66), hover_color=(70, 130, 94),
                   border_color=COLOR_SUCCESS),
        ]
        self.over_buttons = [
            Button((center_x - 170, 452, 340, button_h), "重玩本关 (R)",
                   self.button_action(self.restart_level),
                   base_color=(98, 44, 52), hover_color=(136, 62, 72)),
            Button((center_x - 170, 524, 340, button_h), "返回主菜单 (ESC)",
                   self.button_action(self.back_to_menu)),
        ]

    def button_action(self, action):
        """给按钮回调统一加上"点击音效"。"""
        def wrapped():
            self.audio.play("click")
            action()
        return wrapped

    def toggle_sound(self):
        """开关音效（菜单上的小胶囊按钮 / 游戏内 M 键）。"""
        audible = self.audio.toggle()
        if audible:
            self.audio.play("click")
        self.effects.add_toast("音效已开启" if audible else "音效已关闭",
                               (WINDOW_WIDTH // 2, 120),
                               COLOR_TEXT_DIM if audible else COLOR_DANGER,
                               self.fonts.small)

    def active_buttons(self):
        """当前界面需要响应与绘制的按钮列表。"""
        return {
            self.STATE_MENU: self.menu_buttons,
            self.STATE_PLAY: self.play_buttons,
            self.STATE_CLEAR: self.clear_buttons,
            self.STATE_OVER: self.over_buttons,
        }[self.state]

    # ------------------------------------------------------------------
    # 关卡流程
    # ------------------------------------------------------------------
    def start_new_game(self):
        """从头开始：回到第 1 关，并清空累计得分。"""
        self.total_score = 0
        self.load_level(1)

    def continue_game(self):
        """从菜单继续：进入尚未通关的那一关。"""
        self.load_level(max(self.level_index, 1))

    def load_level(self, index):
        """生成并进入第 index 关。"""
        config, board = generate_level(index, self.rng)
        self.level_index = index
        self.board = board
        self.initial_grid = board.snapshot()
        self.layout = renderer.Layout(board.rows, board.cols)
        self.arrow_total = board.remaining
        self.mistakes_total = config.mistakes
        self.mistakes_left = config.mistakes
        self.score = 0
        self.hover_cell = None
        self.auto_next_timer = 0.0
        self.fail_pending = False
        self.shake.clear()
        self.effects.clear()
        self.state = self.STATE_PLAY
        self.audio.play("start")       # 进入关卡的提示音

    def restart_level(self):
        """重新开始当前关卡：棋盘还原为出题时的初始局面。"""
        if self.board is None or self.initial_grid is None:
            return
        self.board.restore(self.initial_grid)
        self.mistakes_left = self.mistakes_total
        self.score = 0
        self.hover_cell = None
        self.auto_next_timer = 0.0
        self.fail_pending = False
        self.shake.clear()
        self.effects.clear()
        self.state = self.STATE_PLAY

    def next_level(self):
        """进入下一关。"""
        self.load_level(self.level_index + 1)

    def back_to_menu(self):
        """返回开始界面；若当前停在通关界面，则记为已通关并推进关卡游标。"""
        if self.state == self.STATE_CLEAR:
            self.level_index += 1
        self.state = self.STATE_MENU
        self.hover_cell = None
        self.effects.clear()

    def quit_game(self):
        """退出游戏。"""
        self.running = False

    # ------------------------------------------------------------------
    # 点击处理
    # ------------------------------------------------------------------
    def handle_board_click(self, pos):
        """处理棋盘上的一次点击：飞出 / 碰撞 / 无反应。"""
        if self.board is None or self.layout is None:
            return
        if self.state != self.STATE_PLAY or self.fail_pending:
            return                       # 等待切到失败界面期间不再接受操作
        cell = self.layout.cell_at(pos)
        if cell is None:
            return
        row, col = cell
        result = self.board.click(row, col)
        if result.kind == "empty":
            return
        rect = self.layout.cell_rect(row, col)
        if result.kind == "fly":
            self.fire_arrow(row, col, rect)
        else:
            self.hit_blocker(row, col, rect, result.blocker)

    def fire_arrow(self, row, col, rect):
        """箭头飞出：从棋盘移除、播放飞行动画、加分，清空则通关。"""
        direction = self.board.get(row, col)
        self.board.remove(row, col)
        self.audio.play("shoot")
        self.score += SCORE_PER_ARROW
        arrow_font = self.fonts.get(int(self.layout.cell * 0.66), bold=True)
        self.effects.add_flying_arrow(
            rect.center, direction, self.fly_distance(row, col, direction),
            ARROW_COLORS[direction], arrow_font,
        )
        if self.board.remaining == 0:
            self.on_level_clear()

    def hit_blocker(self, row, col, rect, blocker):
        """撞上阻挡：扣 1 次失误、扣分、播碰撞反馈；失误归零则本关失败。"""
        self.mistakes_left -= 1
        self.score = max(0, self.score - SCORE_PER_MISTAKE)
        self.audio.play("block")
        # 记录"晃动的箭头坐标 + 动画起始帧"，绘制时据此计算偏移
        self.shake.start((row, col), self.frame_count)
        self.effects.add_blocked((row, col), rect, blocker,
                                 self.layout.cell_rect(*blocker))
        self.effects.add_toast(f"被挡住了！失误剩余 {max(self.mistakes_left, 0)}",
                               rect.center, COLOR_DANGER, self.fonts.small)
        if self.mistakes_left <= 0:
            # 失误归零：标记待失败，等晃动动画播完由 update() 自动切换界面
            center = self.layout.board_rect.center
            self.effects.add_toast("失误耗尽，本关失败！", center, COLOR_DANGER,
                                   self.fonts.body, duration=SHAKE_DURATION + 0.6)
            self.fail_pending = True

    def fly_distance(self, row, col, direction):
        """飞出动画的位移距离：足够离开棋盘再多飞一格。"""
        d_row, d_col = DIRECTION_VECTORS[direction]
        if d_row:
            steps = (row + 1) if d_row < 0 else (self.board.rows - row)
        else:
            steps = (col + 1) if d_col < 0 else (self.board.cols - col)
        return (steps + 1.6) * self.layout.cell

    def on_level_clear(self):
        """通关：累计得分、记录最高关卡，并启动自动进入下一关的倒计时。"""
        self.best_level = max(self.best_level, self.level_index)
        self.total_score += self.score
        self.audio.play("clear")
        self.auto_next_timer = AUTO_NEXT_DELAY
        self.state = self.STATE_CLEAR

    def on_level_failed(self):
        """失败：把本关得分计入累计，切到失败界面。"""
        self.total_score += self.score
        self.audio.play("fail")
        self.state = self.STATE_OVER

    # ------------------------------------------------------------------
    # 事件、更新与绘制
    # ------------------------------------------------------------------
    def handle_events(self):
        """处理一帧内的所有事件。"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return
            if event.type == pygame.KEYDOWN:
                self.handle_key(event.key)
                continue
            # 先交给按钮；按钮吃掉事件后就不再落到棋盘上
            consumed = False
            for button in self.active_buttons():
                if button.handle_event(event):
                    consumed = True
            if consumed:
                continue
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.handle_board_click(event.pos)
            elif event.type == pygame.MOUSEMOTION and self.state == self.STATE_PLAY:
                self.hover_cell = self.layout.cell_at(event.pos) if self.layout else None

    def handle_key(self, key):
        """键盘快捷键：ESC 返回/退出、R 重开、空格 开始或继续、H 开关辅助线。"""
        if key == pygame.K_ESCAPE:
            if self.state == self.STATE_MENU:
                self.quit_game()
            else:
                self.back_to_menu()
        elif key == pygame.K_r and self.state in (self.STATE_PLAY, self.STATE_OVER):
            self.audio.play("click")
            self.restart_level()
        elif key == pygame.K_m:
            self.toggle_sound()
        elif key == pygame.K_h:
            self.show_hint = not self.show_hint
        elif key in (pygame.K_SPACE, pygame.K_RETURN):
            if self.state == self.STATE_MENU:
                self.audio.play("click")
                self.start_new_game()
            elif self.state == self.STATE_CLEAR:
                self.audio.play("click")
                self.next_level()
            elif self.state == self.STATE_OVER:
                self.audio.play("click")
                self.restart_level()

    def update(self, dt):
        """推进帧计数、晃动动画、特效与各类计时器。"""
        self.frame_count += 1              # 帧计数：所有帧驱动动画的时间基准
        self.shake.update(self.frame_count)  # 播完的晃动动画在这里被清理
        self.effects.update(dt)
        mouse_pos = pygame.mouse.get_pos()
        for button in self.active_buttons():
            was_hovered = button.hovered
            button.set_mouse_pos(mouse_pos)
            if button.hovered and not was_hovered:
                self.audio.play("hover")   # 鼠标刚划到按钮上时给一声轻响

        if self.state == self.STATE_MENU:
            self.menu_scene.update(dt, self.fonts)   # 背景飘动 + 演示棋盘

        if self.state == self.STATE_CLEAR:
            self.auto_next_timer -= dt
            if self.auto_next_timer <= 0:
                self.next_level()          # 通关后自动进入下一关
        elif self.state == self.STATE_PLAY and self.fail_pending:
            # 失误归零后，等左右晃动动画播完（0.3 秒 = 18 帧）再切失败界面
            if not self.shake.is_active():
                self.on_level_failed()

    def build_hud(self):
        """组装顶部信息条所需的数据。"""
        return renderer.Hud(
            level=self.level_index,
            arrow_total=self.arrow_total,
            arrow_left=self.board.remaining if self.board else 0,
            mistakes_left=max(self.mistakes_left, 0),
            mistakes_total=self.mistakes_total,
            score=self.score,
        )

    def draw(self):
        """按当前状态绘制画面。"""
        if self.state == self.STATE_MENU:
            self.menu_buttons[1].text = f"继续第 {max(self.level_index, 1)} 关"
            self.menu_buttons[1].enabled = self.best_level >= 1
            self.menu_buttons[3].text = self.audio.status_text()
            self.menu_buttons[3].enabled = self.audio.ready
            renderer.draw_menu(self.screen, self.fonts, self.best_level,
                               self.total_score, self.menu_scene)
            self.effects.draw_overlay_layer(self.screen)   # 主菜单也能看到提示文字
        else:
            hud = self.build_hud()
            renderer.draw_game(self.screen, self.fonts, self.layout, self.board,
                               self.effects, self.hover_cell, hud, self.show_hint,
                               self.shake, self.frame_count)
            if self.state == self.STATE_CLEAR:
                ratio = self.auto_next_timer / AUTO_NEXT_DELAY
                renderer.draw_level_clear(self.screen, self.fonts, hud, ratio,
                                          self.level_index + 1)
            elif self.state == self.STATE_OVER:
                renderer.draw_game_over(self.screen, self.fonts, hud)
            self.effects.draw_overlay_layer(self.screen)

        for button in self.active_buttons():
            button.draw(self.screen, self.fonts)

    def run(self):
        """主循环：事件 -> 更新 -> 绘制。"""
        try:
            while self.running:
                dt = min(self.clock.tick(FPS) / 1000.0, MAX_DT)
                self.handle_events()
                self.update(dt)
                self.draw()
                pygame.display.flip()
        finally:
            pygame.quit()
