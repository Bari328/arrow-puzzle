# -*- coding: utf-8 -*-
"""离线截图脚本：把四个界面渲染成 PNG，用于人工检查排版与配色。"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # 仓库根目录（tests 的上一级）
SHOTS = os.path.join(ROOT, "screenshots")
sys.path.insert(0, ROOT)

import pygame

from game.app import App


def save(app, name):
    """渲染一帧并保存截图。"""
    app.draw()
    path = os.path.join(SHOTS, name)
    pygame.image.save(app.screen, path)
    print("saved", path)


def advance_menu(app, seconds):
    """推进开始界面，停在"演示棋盘正好有一支箭在飞"的时刻，截图更生动。"""
    for _ in range(int(seconds * 60)):
        app.update(1 / 60)
        flyers = app.menu_scene.demo.effects.flyers
        if flyers and 0.15 <= flyers[0].elapsed / flyers[0].duration <= 0.6:
            return


def main():
    os.makedirs(SHOTS, exist_ok=True)
    app = App(seed=20260917)

    # ---- 开始界面（背景飘动 + 实时演示）----
    app.state = App.STATE_MENU
    advance_menu(app, 4.0)
    save(app, "01_menu.png")

    # ---- 游戏界面：悬停一个被挡住的箭头 ----
    app.load_level(6)
    blocked = [pos for pos in app.board.arrow_positions() if not app.board.can_fly(*pos)]
    if blocked:
        app.hover_cell = blocked[0]
    save(app, "02_play_blocked.png")

    # ---- 游戏界面：悬停一个可以飞出的箭头 ----
    free = app.board.free_arrows()
    app.hover_cell = free[0] if free else None
    save(app, "03_play_free.png")

    # ---- 飞出动画与碰撞晃动（帧驱动：取晃动幅度接近最大的那一帧）----
    app.hover_cell = None
    if free:
        row, col = free[0]
        app.handle_board_click(app.layout.cell_rect(row, col).center)
    if blocked:
        row, col = blocked[0]
        app.handle_board_click(app.layout.cell_rect(row, col).center)
    for _ in range(2):
        app.update(1 / 60)
    save(app, "04_effects.png")

    # ---- 通关界面 ----
    app = App(seed=5)
    app.load_level(1)
    clicks = 0
    while app.state == App.STATE_PLAY and clicks < 4000:
        clicks += 1
        candidates = app.board.free_arrows()
        if not candidates:
            break
        row, col = candidates[0]
        app.handle_board_click(app.layout.cell_rect(row, col).center)
    app.update(0.9)
    save(app, "05_level_clear.png")

    # ---- 失败界面 ----
    app = App(seed=9)
    app.load_level(8)
    blocked = [pos for pos in app.board.arrow_positions() if not app.board.can_fly(*pos)]
    guard = 0
    while app.state == App.STATE_PLAY and blocked and guard < 20:
        guard += 1
        app.handle_board_click(app.layout.cell_rect(*blocked[-1]).center)
        app.update(1 / 60)
    save(app, "07_fail_feedback.png")
    for _ in range(20):
        app.update(1 / 60)
    save(app, "06_game_over.png")

    pygame.quit()


if __name__ == "__main__":
    main()
