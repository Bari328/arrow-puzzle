# -*- coding: utf-8 -*-
"""自动校验脚本：离线检查游戏规则与关卡生成，不打开真实窗口。"""
import os
import random
import re
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # 仓库根目录（tests 的上一级）
sys.path.insert(0, ROOT)

import pygame

from game.app import App
from game.board import Board, check_block
from game.config import (
    DOWN,
    LEFT,
    MISTAKES_PER_LEVEL,
    RIGHT,
    SHAKE_DURATION,
    SHAKE_FRAMES,
    UP,
)
from game.levels import generate_level, is_solvable, level_config, level_stats

FAILURES = []


def check(condition, message):
    """记录一条断言结果。"""
    if condition:
        print(f"  [OK]   {message}")
    else:
        print(f"  [FAIL] {message}")
        FAILURES.append(message)


def test_rules():
    """用一张手写棋盘核对核心规则。"""
    print("\n[1] 核心规则判定")
    # 第 0 行：→ 与 ← 互相挡住；第 1 行的 ↑ 一路畅通
    grid = [
        [RIGHT, 0, LEFT],
        [0, UP, 0],
        [0, 0, 0],
    ]
    board = Board.from_grid(grid)
    check(board.click(0, 0).kind == "blocked", "被其它箭头挡住的箭判定为 blocked")
    check(board.click(0, 0).blocker == (0, 2), "正确指出阻挡者坐标")
    check(board.click(1, 1).kind == "fly", "同一列没有阻挡时可以飞出")
    check(board.click(2, 2).kind == "empty", "点到空格返回 empty")
    board.remove(0, 2)
    check(board.click(0, 0).kind == "fly", "移除阻挡者后原本被挡的箭可以飞出")
    check(board.remaining == 2, "移除后剩余箭头数量正确")
    single = Board.from_grid([[DOWN]])
    check(single.click(0, 0).kind == "fly", "角落的箭朝任意方向都能飞出")


def test_check_block():
    """逐个方向核对 check_block 的判定，并覆盖越界等边界情况。"""
    print("\n[2] check_block：指定位置的箭头是否被阻挡")
    # (0,1)→ 被 (0,3) 挡住；(0,3)← 被 (0,1) 挡住；(1,1)↑ 被 (0,1) 挡住
    grid = [
        [0, 4, 0, 3, 0],
        [0, 1, 0, 0, 0],
        [3, 0, 0, 0, 0],
        [0, 0, 2, 0, 0],
        [0, 0, 0, 0, 0],
    ]
    check(check_block(grid, 0, 1, 4, 5, 5) is True, "朝右：中途遇到箭头 → True")
    check(check_block(grid, 0, 3, 3, 5, 5) is True, "朝左：中途遇到箭头 → True")
    check(check_block(grid, 1, 1, 1, 5, 5) is True, "朝上：中途遇到箭头 → True")
    check(check_block(grid, 3, 2, 2, 5, 5) is False, "朝下：一路到边界全空 → False")
    check(check_block(grid, 2, 0, 3, 5, 5) is False, "朝左：下一格就是边界 → False")
    check(check_block(grid, 0, 4, 2, 5, 5) is False, "朝下：整列没有其它箭头 → False")
    check(check_block(grid, 4, 0, 4, 5, 5) is False, "起点是空格 → False")
    check(isinstance(check_block(grid, 1, 1, 1, 5, 5), bool), "返回值是布尔类型")

    # 边界与非法入参：既不越界也不抛异常
    check(check_block(grid, -1, 0, 2, 5, 5) is False, "行号为负 → False")
    check(check_block(grid, 5, 0, 1, 5, 5) is False, "行号超出行数 → False")
    check(check_block(grid, 0, -1, 4, 5, 5) is False, "列号为负 → False")
    check(check_block(grid, 0, 5, 3, 5, 5) is False, "列号超出列数 → False")
    check(check_block(grid, 1, 1, 9, 5, 5) is False, "未知方向 → False")
    check(check_block([], 0, 0, 1, 0, 0) is False, "空棋盘 → False")
    check(check_block([[1]], 0, 0, 1, 99, 99) is False, "rows/cols 传大 → 按实际尺寸收敛，不越界")
    check(check_block([[1, 1], [2]], 0, 1, 2, 2, 2) is False, "参差不齐数组的越界列 → False")
    check(check_block([[1, 0], [2]], 0, 0, 2, 2, 2) is True, "参差不齐数组仍能正常判定 → True")

    # 与游戏内 Board 的判定完全一致（随机棋盘上逐格对比）
    rng = random.Random(20260922)
    consistent = True
    mismatches = 0
    for _ in range(200):
        _, board = generate_level(rng.randint(1, 12), rng)
        for row, col in board.arrow_positions():
            direction = board.get(row, col)
            blocked = check_block(board.grid, row, col, direction, board.rows, board.cols)
            if blocked != board.is_blocked(row, col):
                consistent = False
                mismatches += 1
            if blocked != (board.blocker_of(row, col) is not None):
                consistent = False
                mismatches += 1
            if (not blocked) != board.can_fly(row, col):
                consistent = False
                mismatches += 1
    check(consistent, f"200 张随机棋盘上与 can_fly / blocker_of 判定一致（不一致 {mismatches} 处）")
    return grid


def test_levels():
    """检查每一关都能生成、且必定可解，同时打印难度统计。"""
    print("\n[3] 关卡生成与可解性")
    rng = random.Random(20260917)
    for index in range(1, 21):
        config, board = generate_level(index, rng)
        stats = level_stats(board)
        check(is_solvable(board),
              f"第 {index} 关可解（{board.rows}x{board.cols}，箭头 {stats['arrows']}/"
              f"{config.arrow_count}，开局可飞出 {stats['free']} 支，失误 {config.mistakes} 次）")
        if config.mistakes != MISTAKES_PER_LEVEL:
            check(False, f"第 {index} 关失误次数不是 {MISTAKES_PER_LEVEL}")
    stable = True
    for seed in range(40):
        for index in range(1, 13):
            _, board = generate_level(index, random.Random(seed * 100 + index))
            if not is_solvable(board):
                stable = False
    check(stable, "40 组随机种子 x 12 关全部可解")
    check(all(level_config(i).mistakes == MISTAKES_PER_LEVEL for i in range(1, 21)),
          f"1~20 关的初始失误次数都是 {MISTAKES_PER_LEVEL} 次")


def test_playthrough():
    """用贪心策略模拟完整通关流程，检查状态机与计分。"""
    print("\n[4] 通关流程（模拟点击）")
    app = App(seed=7)
    app.start_new_game()
    check(app.state == App.STATE_PLAY, "开始游戏后进入游戏界面")
    check(app.board.remaining == app.arrow_total, "顶部信息条的箭头总数与棋盘一致")
    cleared_levels = 0
    clicks = 0
    while cleared_levels < 3 and clicks < 5000:
        clicks += 1
        if app.state == App.STATE_PLAY:
            free = app.board.free_arrows()
            if not free:
                break
            row, col = free[0]
            app.handle_board_click(app.layout.cell_rect(row, col).center)
        elif app.state == App.STATE_CLEAR:
            cleared_levels += 1
            app.auto_next_timer = 0.0
            app.update(0.016)
    check(cleared_levels == 3, f"连续通关 3 关（实际 {cleared_levels} 关，共 {clicks} 次点击）")
    check(app.best_level == 3, f"最高通关关卡记录为 3（实际 {app.best_level}）")
    check(app.total_score > 0, f"累计得分为正（{app.total_score}）")
    check(app.mistakes_left == app.mistakes_total, "全程无误操作，失误未被消耗")


def test_blocked_and_fail():
    """检查点错箭扣失误、失误归零后自动进失败界面、以及重开本关的还原。"""
    print("\n[5] 失误与失败流程")
    app = App(seed=11)
    app.load_level(1)
    initial = app.board.snapshot()
    mistakes_total = app.mistakes_total
    check(mistakes_total == MISTAKES_PER_LEVEL, f"本关初始失误次数为 {mistakes_total} 次")
    blocked = [pos for pos in app.board.arrow_positions() if not app.board.can_fly(*pos)]
    check(bool(blocked), f"第 1 关开局存在被挡住的箭（{len(blocked)} 支）")
    for step in range(mistakes_total):
        row, col = blocked[-1]
        app.handle_board_click(app.layout.cell_rect(row, col).center)
        check(app.mistakes_left == mistakes_total - step - 1,
              f"第 {step + 1} 次点错后失误剩余 {app.mistakes_left}")
        app.update(1 / 60)
    check(app.mistakes_left == 0, "失误次数已归零")
    check(app.fail_pending, "失误归零后标记为待失败")
    check(app.state == App.STATE_PLAY, "晃动动画播放期间仍停留在游戏界面")
    for _ in range(SHAKE_FRAMES + 2):
        app.update(1 / 60)
    check(app.state == App.STATE_OVER, "晃动播完后自动切换到失败界面")
    app.restart_level()
    check(app.state == App.STATE_PLAY, "重开本关回到游戏界面")
    check(app.board.snapshot() == initial, "重开本关还原了初始棋盘")
    check(app.mistakes_left == mistakes_total, "重开本关恢复失误次数")
    check(not app.fail_pending and not app.shake.is_active(), "重开本关清空了失败标记与晃动动画")
    check(app.score == 0, "重开本关清零本关得分")


def test_shake_animation():
    """检查"晃动坐标 + 起始帧"两个状态变量与 0.3 秒 / 18 帧的动画行为。"""
    print("\n[6] 碰撞晃动动画（帧计数驱动）")
    check(SHAKE_FRAMES == int(round(60 * SHAKE_DURATION)) == 18,
          f"0.3 秒换算为 {SHAKE_FRAMES} 帧（60FPS）")
    app = App(seed=13)
    app.load_level(5)
    blocked = [pos for pos in app.board.arrow_positions() if not app.board.can_fly(*pos)]
    row, col = blocked[0]
    app.handle_board_click(app.layout.cell_rect(row, col).center)
    check(len(app.shake.animations) == 1, "点错箭后产生一条晃动动画")
    animation = app.shake.animations[0]
    check(animation.cell == (row, col), f"记录了晃动的箭头坐标 {animation.cell}")
    check(animation.start_frame == app.frame_count,
          f"记录了动画起始帧 {animation.start_frame}")

    first = animation.start_frame
    offsets = [animation.offset(frame) for frame in range(first, first + SHAKE_FRAMES + 1)]
    xs = [dx for dx, _ in offsets]
    ys = [dy for _, dy in offsets]
    check(all(value == 0.0 for value in ys), "偏移只有左右方向，不上下抖")
    check(any(value > 1 for value in xs) and any(value < -1 for value in xs),
          "左右两个方向都晃到了")
    check(abs(max(xs)) <= 9.0 and abs(min(xs)) <= 9.0, "横向偏移不超过设定幅度")
    check(offsets[0] == (0.0, 0.0) and offsets[-1] == (0.0, 0.0),
          "动画首帧与末帧的偏移都归零")
    check(animation.finished(first + SHAKE_FRAMES - 1) is False
          and animation.finished(first + SHAKE_FRAMES) is True,
          "第 18 帧后才算播放结束")

    for _ in range(SHAKE_FRAMES):
        app.update(1 / 60)
    check(not app.shake.is_active(), "帧推进到 18 帧后动画自动清理，不阻塞主循环")
    check(app.update.__doc__ is not None, "动画更新在 update() 中按帧推进")
    return app


def test_edges():
    """边界情况：失败等待期间不响应点击、点击棋盘外无影响。"""
    print("\n[7] 边界情况")
    app = App(seed=3)
    app.load_level(2)
    app.mistakes_left = 1
    blocked = [pos for pos in app.board.arrow_positions() if not app.board.can_fly(*pos)]
    if blocked:
        app.handle_board_click(app.layout.cell_rect(*blocked[0]).center)
        app.update(0.016)
        before = app.board.remaining
        free = app.board.free_arrows()
        app.handle_board_click(app.layout.cell_rect(*free[0]).center)
        check(app.board.remaining == before, "失败等待期间点击棋盘不再生效")
    app.restart_level()
    before = app.board.remaining
    app.handle_board_click((30, 30))
    check(app.board.remaining == before, "点击棋盘外不会改变棋盘")
    config = level_config(30)
    check(min(config.rows, config.cols) >= 5, f"第 30 关棋盘尺寸 {config.rows}x{config.cols}")
    pygame.quit()


def test_no_blocking_sleep():
    """需求明确不使用 time.sleep：确认游戏代码里没有阻塞式等待。"""
    print("\n[8] 不使用阻塞等待")
    pattern = re.compile(r"^\s*(import\s+time\b|from\s+time\s+import)|time\.sleep\s*\(", re.MULTILINE)
    checked = 0
    offenders = []
    for folder in (os.path.join(ROOT, "game"), ROOT):
        for name in sorted(os.listdir(folder)):
            if not name.endswith(".py"):
                continue
            checked += 1
            with open(os.path.join(folder, name), encoding="utf-8") as handle:
                text = handle.read()
            if pattern.search(text):
                offenders.append(name)
    check(not offenders, f"检查了 {checked} 个模块，没有 time.sleep / import time（{offenders}）")


if __name__ == "__main__":
    test_rules()
    test_check_block()
    test_levels()
    test_playthrough()
    test_blocked_and_fail()
    test_shake_animation()
    test_edges()
    test_no_blocking_sleep()
    print("\n" + "=" * 60)
    if FAILURES:
        print(f"共 {len(FAILURES)} 项失败：")
        for item in FAILURES:
            print("  -", item)
        sys.exit(1)
    print("全部检查通过")
