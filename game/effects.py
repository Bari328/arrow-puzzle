# -*- coding: utf-8 -*-
"""特效模块：箭头飞出、碰撞闪光、浮动提示文字。

每种特效自己维护生命周期，由 Effects 统一 update / draw；
主程序在事件发生时只需要"添加"特效，画面细节都收在这里。

注意：被撞箭头的"左右晃动"由 animation.py 用帧计数实现（见 ShakeManager），
这里只负责碰撞时的红/橙描边闪光与提示文字。
"""

import pygame

from .config import (
    COLOR_BLOCKER,
    COLOR_DANGER,
    COLOR_TEXT,
    DIRECTION_GLYPHS,
    DIRECTION_VECTORS,
)


def ease_out(progress):
    """缓出曲线：先快后慢。"""
    return 1.0 - (1.0 - progress) ** 3


class FlyingArrow:
    """成功射出的箭头：沿箭头方向加速飞出棋盘，同时淡出。"""

    def __init__(self, center, direction, distance, color, font, duration=0.42):
        self.start = pygame.Vector2(center)
        self.direction = direction
        self.distance = distance
        self.color = color
        self.font = font
        self.duration = duration
        self.elapsed = 0.0
        # 预先渲染好字符，避免每帧重复渲染
        self.image = font.render(DIRECTION_GLYPHS[direction], True, color)

    @property
    def alive(self):
        """特效是否还需要继续播放。"""
        return self.elapsed < self.duration

    def update(self, dt):
        self.elapsed += dt

    def draw(self, surface):
        progress = min(self.elapsed / self.duration, 1.0)
        d_row, d_col = DIRECTION_VECTORS[self.direction]
        travel = self.distance * ease_out(progress)
        center = (int(self.start.x + d_col * travel), int(self.start.y + d_row * travel))
        image = self.image.copy()
        image.set_alpha(int(255 * (1.0 - progress ** 1.6)))
        surface.blit(image, image.get_rect(center=center))


class BlockedFlash:
    """碰撞反馈：被点的格子闪红框，挡住它的箭头闪橙框（时间驱动）。"""

    def __init__(self, cell, cell_rect, blocker, blocker_rect, duration=0.5):
        self.cell = cell
        self.cell_rect = pygame.Rect(cell_rect)
        self.blocker = blocker
        self.blocker_rect = pygame.Rect(blocker_rect)
        self.duration = duration
        self.elapsed = 0.0

    @property
    def alive(self):
        return self.elapsed < self.duration

    def update(self, dt):
        self.elapsed += dt

    def draw(self, surface):
        progress = min(self.elapsed / self.duration, 1.0)
        alpha = int(215 * (1.0 - progress))
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        # 被点格子：红色填充 + 描边
        pygame.draw.rect(overlay, (*COLOR_DANGER, alpha // 5), self.cell_rect, border_radius=10)
        pygame.draw.rect(overlay, (*COLOR_DANGER, alpha), self.cell_rect, width=4, border_radius=10)
        # 阻挡者：橙色描边，让玩家知道"是谁挡的"
        pygame.draw.rect(overlay, (*COLOR_BLOCKER, alpha), self.blocker_rect, width=4, border_radius=10)
        surface.blit(overlay, (0, 0))


class Toast:
    """上浮的提示文字，例如"被挡住了！失误 -1"。"""

    def __init__(self, text, position, color=COLOR_TEXT, font=None, duration=1.1, rise=38):
        self.text = text
        self.position = position
        self.color = color
        self.font = font
        self.duration = duration
        self.rise = rise
        self.elapsed = 0.0
        self.image = font.render(text, True, color) if font else None

    @property
    def alive(self):
        return self.elapsed < self.duration

    def update(self, dt):
        self.elapsed += dt

    def draw(self, surface):
        if self.image is None:
            return
        progress = min(self.elapsed / self.duration, 1.0)
        image = self.image.copy()
        image.set_alpha(int(255 * (1.0 - progress ** 2)))
        x, y = self.position
        center = (int(x), int(y - self.rise * ease_out(progress)))
        surface.blit(image, image.get_rect(center=center))


class Effects:
    """统一管理所有特效的更新与绘制。"""

    def __init__(self):
        self.flyers = []
        self.flashes = []
        self.toasts = []

    # ------------------------- 添加特效 -------------------------
    def clear(self):
        """清空所有特效（切换关卡时使用）。"""
        self.flyers.clear()
        self.flashes.clear()
        self.toasts.clear()

    def add_flying_arrow(self, center, direction, distance, color, font, duration=0.42):
        self.flyers.append(FlyingArrow(center, direction, distance, color, font, duration))

    def add_blocked(self, cell, cell_rect, blocker, blocker_rect):
        self.flashes.append(BlockedFlash(cell, cell_rect, blocker, blocker_rect))

    def add_toast(self, text, position, color=COLOR_TEXT, font=None, duration=1.1):
        if font is not None:
            self.toasts.append(Toast(text, position, color, font, duration))

    # ------------------------- 更新与查询 -------------------------
    def update(self, dt):
        for group in (self.flyers, self.flashes, self.toasts):
            for item in group:
                item.update(dt)
        self.flyers = [item for item in self.flyers if item.alive]
        self.flashes = [item for item in self.flashes if item.alive]
        self.toasts = [item for item in self.toasts if item.alive]

    # ------------------------- 绘制 -------------------------
    def draw_board_layer(self, surface):
        """与棋盘同层的特效：碰撞框 + 飞出的箭头。"""
        for flash in self.flashes:
            flash.draw(surface)
        for flyer in self.flyers:
            flyer.draw(surface)

    def draw_overlay_layer(self, surface):
        """最上层的特效：浮动提示文字。"""
        for toast in self.toasts:
            toast.draw(surface)
