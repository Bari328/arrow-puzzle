# -*- coding: utf-8 -*-
"""关卡生成与可解性校验。

核心思路是"逆向构造法"：
先把棋盘当成空的（相当于所有箭都已经射出），再按"被射掉的顺序"倒着把箭放回去。
放回一支箭时，要求它前方到边界之间全为空——这正好等价于正着玩时它可以飞出。
于是按放回顺序的逆序点击，必然能清空棋盘，题目一定可解。
"""

import random
from collections import namedtuple

from .board import Board, path_is_clear
from .config import ALL_DIRECTIONS, EMPTY, MISTAKES_PER_LEVEL

# 关卡配置：序号 / 行数 / 列数 / 箭头数量 / 允许的失误次数
LevelConfig = namedtuple("LevelConfig", "index rows cols arrow_count mistakes")


def level_config(index):
    """按关卡序号给出难度配置：棋盘逐渐变大、箭头变密、容错变少。"""
    size = min(5 + (index - 1) // 3, 9)              # 5,5,5,6,6,6,7,7,7,8,8,8,9...
    density = min(0.30 + 0.06 * (index - 1), 0.62)   # 箭头密度上限
    arrow_count = int(round(size * size * density))
    arrow_count = max(4, min(arrow_count, size * size - 1))
    mistakes = MISTAKES_PER_LEVEL       # 每关初始失误次数（需求：固定 3 次）
    return LevelConfig(index, size, size, arrow_count, mistakes)


def _placeable_positions(grid, rows, cols):
    """枚举所有"放回去就合法"的落点，返回 (行, 列, 方向) 列表。"""
    positions = []
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] != EMPTY:
                continue
            for direction in ALL_DIRECTIONS:
                if path_is_clear(grid, r, c, direction):
                    positions.append((r, c, direction))
    return positions


def generate_board(config, rng=None):
    """按配置逆向构造一张必定可解的棋盘。"""
    rng = rng or random.Random()
    grid = [[EMPTY] * config.cols for _ in range(config.rows)]
    placed = 0
    # 每一步都重新枚举合法落点；棋盘规模很小，开销可以忽略
    while placed < config.arrow_count:
        positions = _placeable_positions(grid, config.rows, config.cols)
        if not positions:
            break        # 已经没有合法落点（棋盘被填满），提前收工
        r, c, direction = rng.choice(positions)
        grid[r][c] = direction
        placed += 1
    return Board.from_grid(grid)


def generate_level(index, rng=None):
    """生成第 index 关，返回 (关卡配置, 棋盘)。"""
    config = level_config(index)
    return config, generate_board(config, rng)


def is_solvable(board):
    """用贪心模拟校验棋盘是否可解。

    只要某支箭当前路径畅通就立刻射掉它：因为移除箭头只会让其它箭头的路更通畅，
    "现在能飞的以后一定能飞"，所以贪心不会错过可行解。
    """
    work = board.clone()
    while work.remaining:
        free = work.free_arrows()
        if not free:
            return False
        for position in free:
            work.remove(*position)
    return True


def level_stats(board):
    """统计一张棋盘的难度信息，便于调试与调参。"""
    free = board.free_arrows()
    return {
        "arrows": board.remaining,
        "free": len(free),
        "free_ratio": (len(free) / board.remaining) if board.remaining else 0.0,
    }
