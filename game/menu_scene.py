# -*- coding: utf-8 -*-
"""开始界面的动态画面：背景飘动箭头 + 实时演示小棋盘。

两部分都只依赖帧循环传入的 dt，不需要任何外部素材：
    DriftingArrow  背景里缓慢飘动的箭头，飘出画面后从另一侧绕回来
    DemoBoard      右侧卡片里的"实时演示"小棋盘，会自动射箭、自动补位
    MenuScene      把上面两部分打包，供 renderer.draw_menu() 调用
"""

import random

import pygame

from . import renderer
from .board import check_block
from .config import (
    ALL_DIRECTIONS,
    ARROW_COLORS,
    DIRECTION_VECTORS,
    EMPTY,
    MENU_DEMO_CELL,
    MENU_DEMO_COLS,
    MENU_DEMO_FILL,
    MENU_DEMO_INTERVAL,
    MENU_DEMO_ROWS,
    MENU_PARTICLE_ALPHA,
    MENU_PARTICLE_COUNT,
    MENU_PARTICLE_SIZE,
    MENU_PARTICLE_SPEED,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)
from .effects import Effects


class DriftingArrow:
    """背景里缓慢飘动的箭头，飘出画面后从另一侧绕回来。"""

    def __init__(self, rng):
        self.direction = rng.choice(ALL_DIRECTIONS)
        self.size = rng.randint(*MENU_PARTICLE_SIZE)
        self.alpha = rng.randint(*MENU_PARTICLE_ALPHA)
        self.speed = rng.uniform(*MENU_PARTICLE_SPEED)
        self.x = rng.uniform(0, WINDOW_WIDTH)
        self.y = rng.uniform(0, WINDOW_HEIGHT)
        self.phase = rng.uniform(0.0, 6.283)

    def update(self, dt):
        """沿自己的箭头方向慢慢飘，出画后从对面绕回来。"""
        d_row, d_col = DIRECTION_VECTORS[self.direction]
        self.x += d_col * self.speed * dt
        self.y += d_row * self.speed * dt
        margin = self.size
        if self.x < -margin:
            self.x = WINDOW_WIDTH + margin
        elif self.x > WINDOW_WIDTH + margin:
            self.x = -margin
        if self.y < -margin:
            self.y = WINDOW_HEIGHT + margin
        elif self.y > WINDOW_HEIGHT + margin:
            self.y = -margin

    def draw(self, surface, fonts):
        image = renderer.make_arrow_image(fonts, self.direction, self.size,
                                          ARROW_COLORS[self.direction])
        image = image.copy()
        image.set_alpha(self.alpha)
        surface.blit(image, image.get_rect(center=(int(self.x), int(self.y))))


class DemoBoard:
    """开始界面右侧的实时演示小棋盘：自动射出一支能飞出的箭，再补一支新的。"""

    def __init__(self, rng=None, rows=MENU_DEMO_ROWS, cols=MENU_DEMO_COLS,
                 cell=MENU_DEMO_CELL):
        self.rng = rng or random.Random()
        self.rows = rows
        self.cols = cols
        self.cell = cell
        self.width = cols * cell
        self.height = rows * cell
        self.grid = [[EMPTY] * cols for _ in range(rows)]
        self.effects = Effects()
        self.timer = 0.0
        self.fill_initial()

    # ------------------------- 棋盘内容 -------------------------
    def fill_initial(self):
        """随机铺一批箭头，作为演示的起始局面。"""
        total = self.rows * self.cols
        for _ in range(int(total * MENU_DEMO_FILL)):
            self.add_random_arrow()

    def empty_cells(self, exclude=None):
        """所有空格坐标（可排除某一格）。"""
        return [(r, c)
                for r in range(self.rows)
                for c in range(self.cols)
                if self.grid[r][c] == EMPTY and (r, c) != exclude]

    def add_random_arrow(self, exclude=None):
        """在一个随机空格放一支随机方向的箭头。"""
        cells = self.empty_cells(exclude)
        if not cells:
            return None
        row, col = self.rng.choice(cells)
        self.grid[row][col] = self.rng.choice(ALL_DIRECTIONS)
        return (row, col)

    def free_arrows(self):
        """当前路径畅通、可以飞出的箭头坐标。"""
        return [(r, c)
                for r in range(self.rows)
                for c in range(self.cols)
                if self.grid[r][c] != EMPTY
                and not check_block(self.grid, r, c, self.grid[r][c], self.rows, self.cols)]

    def cell_rect(self, row, col, origin):
        """演示棋盘某格的矩形（origin 是棋盘左上角）。"""
        return pygame.Rect(origin[0] + col * self.cell,
                           origin[1] + row * self.cell,
                           self.cell, self.cell)

    # ------------------------- 循环 -------------------------
    def update(self, dt, fonts):
        """推进演示：到时间就射出一支箭并发动画，然后补一支新的。"""
        self.effects.update(dt)
        self.timer += dt
        if self.timer < MENU_DEMO_INTERVAL:
            return
        self.timer = 0.0
        free = self.free_arrows()
        if free:
            row, col = self.rng.choice(free)
            direction = self.grid[row][col]
            self.grid[row][col] = EMPTY
            rect = pygame.Rect(col * self.cell, row * self.cell, self.cell, self.cell)
            distance = (max(self.rows, self.cols) + 2) * self.cell
            font = fonts.get(int(self.cell * 0.66), bold=True)
            self.effects.add_flying_arrow(rect.center, direction, distance,
                                          ARROW_COLORS[direction], font,
                                          duration=MENU_DEMO_INTERVAL * 0.9)
            self.add_random_arrow(exclude=(row, col))   # 补一支，别刚空就补回原位
        else:
            self.add_random_arrow()                     # 万一全被挡住，补一支新的

    # ------------------------- 绘制 -------------------------
    def draw(self, surface, fonts, origin):
        """在指定位置画出演示棋盘：格子底 + 箭头 + 飞出动画（裁剪在棋盘范围内）。"""
        area = pygame.Rect(origin[0], origin[1], self.width, self.height)
        pygame.draw.rect(surface, (30, 34, 53), area.inflate(12, 12), border_radius=14)
        pygame.draw.rect(surface, (70, 78, 110), area.inflate(12, 12), width=2, border_radius=14)
        for row in range(self.rows):
            for col in range(self.cols):
                inner = self.cell_rect(row, col, origin).inflate(-4, -4)
                pygame.draw.rect(surface, (44, 49, 74), inner, border_radius=8)
        for row in range(self.rows):
            for col in range(self.cols):
                direction = self.grid[row][col]
                if direction == EMPTY:
                    continue
                center = self.cell_rect(row, col, origin).center
                renderer.draw_arrow(surface, fonts, center, direction,
                                    ARROW_COLORS[direction], self.cell)
        previous_clip = surface.get_clip()
        surface.set_clip(area.inflate(16, 16))
        self.effects.draw_board_layer(surface)
        surface.set_clip(previous_clip)


class MenuScene:
    """开始界面的动态元素集合：背景飘动箭头 + 实时演示棋盘。"""

    def __init__(self, rng=None):
        self.rng = rng or random.Random()
        self.arrows = [DriftingArrow(self.rng) for _ in range(MENU_PARTICLE_COUNT)]
        self.demo = DemoBoard(self.rng)

    def update(self, dt, fonts):
        """推进背景飘动与演示棋盘。"""
        for arrow in self.arrows:
            arrow.update(dt)
        self.demo.update(dt, fonts)

    def draw_background(self, surface, fonts):
        """画背景飘动箭头（在卡片之前绘制）。"""
        for arrow in self.arrows:
            arrow.draw(surface, fonts)

    def draw_demo(self, surface, fonts, rect):
        """把演示棋盘居中画进给定区域，返回实际棋盘矩形。"""
        origin = (rect.centerx - self.demo.width // 2,
                  rect.centery - self.demo.height // 2)
        self.demo.draw(surface, fonts, origin)
        return pygame.Rect(origin[0], origin[1], self.demo.width, self.demo.height)
