# -*- coding: utf-8 -*-
"""排版与字形自检：不靠肉眼，用元素矩形和字体度量检查界面是否压字、越界、缺字。"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # 仓库根目录（tests 的上一级）
sys.path.insert(0, ROOT)

import pygame

from game import renderer
from game.app import App
from game.config import WINDOW_HEIGHT, WINDOW_WIDTH

FAILURES = []
WINDOW = pygame.Rect(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT)


def check(condition, message):
    """记录一条断言结果。"""
    if condition:
        print(f"  [OK]   {message}")
    else:
        print(f"  [FAIL] {message}")
        FAILURES.append(message)


def overlap(a, b, slack=4):
    """两块矩形是否真的压在一起（留出 slack 像素容差）。"""
    return a.inflate(-slack, -slack).clip(b.inflate(-slack, -slack)).size != (0, 0)


def check_no_overlap(title, items):
    """检查一组元素两两不重叠。"""
    hits = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            name_a, rect_a = items[i]
            name_b, rect_b = items[j]
            if overlap(rect_a, rect_b):
                hits.append(f"{name_a} × {name_b}")
    check(not hits, f"{title} 元素互不重叠" + (f"（冲突：{hits}）" if hits else ""))


def check_inside(title, rect, container):
    """检查矩形是否完全落在容器里。"""
    ok = (rect.left >= container.left and rect.top >= container.top
          and rect.right <= container.right and rect.bottom <= container.bottom)
    check(ok, f"{title} 在允许范围内（{tuple(rect)} ⊂ {tuple(container)}）")


def test_glyphs():
    """校验所用中文字形与符号在该字体里都存在，避免出现方块字。"""
    print("\n[1] 字形可用性")
    app = App(seed=1)
    font = app.fonts.get(20)
    chars = set()
    for name in os.listdir(os.path.join(ROOT, "game")):
        if not name.endswith(".py"):
            continue
        with open(os.path.join(ROOT, "game", name), encoding="utf-8") as handle:
            chars.update(char for char in handle.read() if ord(char) > 127)
    with open(os.path.join(ROOT, "main.py"), encoding="utf-8") as handle:
        chars.update(char for char in handle.read() if ord(char) > 127)
    missing = sorted(char for char in chars if font.metrics(char)[0] is None)
    check(not missing, f"界面用到的 {len(chars)} 个中文字/符号全部有字形（缺字：{missing}）")
    check(app.fonts.glyphs_ok, "字体包含 ↑↓←→ 四个箭头字符")
    check(app.fonts.path is not None, f"已找到中文字体：{app.fonts.path}")
    return app


def test_menu(app):
    """开始界面排版检查。"""
    print("\n[2] 开始界面")
    elements = renderer.draw_menu(app.screen, app.fonts, 6, 480, app.menu_scene)
    for name, rect in elements.items():
        if not isinstance(rect, pygame.Rect):
            continue
        check_inside(name, rect, WINDOW)
    for name in ("rule_title", "rule_text", "rule_note"):
        check_inside(name, elements[name], elements["rule_card"])
    for name in ("demo_title", "demo_board", "demo_caption"):
        check_inside(name, elements[name], elements["demo_card"])
    check(elements["rule_text"].width <= elements["rule_card"].width - 40,
          f"玩法文案宽 {elements['rule_text'].width}px，没有超出卡片")
    check(elements["demo_board"].width <= elements["demo_card"].width - 30,
          f"演示棋盘宽 {elements['demo_board'].width}px，没有超出卡片")

    buttons = [(f"button{i}", button.rect) for i, button in enumerate(app.menu_buttons)]
    for name, rect in buttons:
        check_inside(name, rect, WINDOW)
    check_no_overlap("标题区/卡片区/按钮区/统计区",
                     [("title", elements["title"]), ("subtitle", elements["subtitle"]),
                      ("ornament", elements["ornament"]), ("rule_card", elements["rule_card"]),
                      ("demo_card", elements["demo_card"]), ("stats", elements["stats"]),
                      ("footer", elements["footer"]), ("tip", elements["tip"])] + buttons)


def test_play(app):
    """游戏界面排版检查（多种棋盘尺寸都要过）。"""
    print("\n[3] 游戏界面")
    for level in (1, 4, 7, 10, 13):
        app.load_level(level)
        app.hover_cell = None
        elements = renderer.draw_game(app.screen, app.fonts, app.layout, app.board,
                                      app.effects, app.hover_cell, app.build_hud())
        size = f"{app.board.rows}x{app.board.cols}"
        hud_texts = [("level_text", elements["level_text"]), ("level_tip", elements["level_tip"]),
                     ("arrow_label", elements["arrow_label"]), ("arrow_bar", elements["arrow_bar"]),
                     ("arrow_percent", elements["arrow_percent"]),
                     ("score_text", elements["score_text"]),
                     ("mistake_label", elements["mistake_label"]),
                     ("mistake_dots", elements["mistake_dots"])]
        check_no_overlap(f"第 {level} 关（{size}）顶部信息条内部", hud_texts)
        for name, rect in hud_texts:
            check_inside(f"第 {level} 关 {name}", rect, elements["hud_panel"])
        check_inside(f"第 {level} 关 底部提示", elements["bottom_hint"], WINDOW)
        check(not overlap(elements["board_frame"], elements["hud_panel"]),
              f"第 {level} 关（{size}）棋盘不与顶部信息条重叠")
        check(not overlap(elements["board_frame"], elements["bottom_hint"]),
              f"第 {level} 关（{size}）棋盘不与底部提示重叠")
        for index, button in enumerate(app.play_buttons):
            check_inside(f"第 {level} 关 按钮{index}", button.rect, WINDOW)
            check(not overlap(elements["board_frame"], button.rect),
                  f"第 {level} 关（{size}）棋盘不与按钮{index}重叠")
            check(not overlap(elements["bottom_hint"], button.rect),
                  f"第 {level} 关（{size}）底部提示不与按钮{index}重叠")
        check(elements["board_frame"].top > elements["hud_panel"].bottom,
              f"第 {level} 关（{size}）棋盘压在信息条下方")
        check(not overlap(app.layout.clip_rect, elements["hud_panel"]),
              f"第 {level} 关（{size}）飞出动画不会被画到信息条上")


def test_clear(app):
    """通关界面排版检查。"""
    print("\n[4] 通关界面")
    app.load_level(2)
    hud = app.build_hud()
    elements = renderer.draw_level_clear(app.screen, app.fonts, hud, 0.6, 3)
    check_inside("面板", elements["panel"], WINDOW)
    for name in ("title", "stars", "stats", "countdown_bar", "countdown_text"):
        check_inside(name, elements[name], elements["panel"])
    check_no_overlap("通关面板内部",
                     [("title", elements["title"]), ("stars", elements["stars"]),
                      ("stats", elements["stats"]), ("countdown_bar", elements["countdown_bar"]),
                      ("countdown_text", elements["countdown_text"])])
    for index, button in enumerate(app.clear_buttons):
        check_inside(f"按钮{index}", button.rect, elements["panel"])
        for name in ("title", "stars", "stats", "countdown_bar", "countdown_text"):
            check(not overlap(button.rect, elements[name]),
                  f"通关按钮{index} 不压住 {name}")


def test_over(app):
    """失败界面排版检查。"""
    print("\n[5] 失败界面")
    app.load_level(2)
    elements = renderer.draw_game_over(app.screen, app.fonts, app.build_hud())
    check_inside("面板", elements["panel"], WINDOW)
    for name in ("title", "stats"):
        check_inside(name, elements[name], elements["panel"])
    check_no_overlap("失败面板内部",
                     [("title", elements["title"]), ("stats", elements["stats"])])
    for index, button in enumerate(app.over_buttons):
        check_inside(f"按钮{index}", button.rect, elements["panel"])
        for name in ("title", "stats"):
            check(not overlap(button.rect, elements[name]),
                  f"失败按钮{index} 不压住 {name}")
    check_no_overlap("失败按钮之间",
                     [(f"button{i}", button.rect) for i, button in enumerate(app.over_buttons)])


if __name__ == "__main__":
    application = test_glyphs()
    test_menu(application)
    test_play(application)
    test_clear(application)
    test_over(application)
    pygame.quit()
    print("\n" + "=" * 60)
    if FAILURES:
        print(f"共 {len(FAILURES)} 项失败")
        for item in FAILURES:
            print("  -", item)
        sys.exit(1)
    print("排版与字形检查全部通过")
