# -*- coding: utf-8 -*-
"""界面小部件：圆角按钮。

按钮只负责"矩形 + 文字 + 悬停/按下状态 + 回调"，
具体每个界面放哪些按钮由 app.py 决定。
"""

import pygame

from .config import (
    COLOR_ACCENT,
    COLOR_BORDER,
    COLOR_PANEL_SOFT,
    COLOR_TEXT,
    COLOR_TEXT_DIM,
)

# 禁用状态下的配色
DISABLED_FILL = (30, 33, 50)
DISABLED_BORDER = (52, 57, 80)


class Button:
    """圆角按钮：支持悬停高亮、禁用状态与点击回调。"""

    def __init__(self, rect, text, action=None, *, font_size=26,
                 base_color=COLOR_PANEL_SOFT, hover_color=COLOR_BORDER,
                 text_color=COLOR_TEXT, border_color=COLOR_BORDER, enabled=True):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.action = action
        self.font_size = font_size
        self.base_color = base_color
        self.hover_color = hover_color
        self.text_color = text_color
        self.border_color = border_color
        self.enabled = enabled
        self.hovered = False
        self.pressed = False

    def set_mouse_pos(self, pos):
        """每帧更新悬停状态。"""
        self.hovered = bool(self.enabled and self.rect.collidepoint(pos))

    def handle_event(self, event):
        """处理鼠标事件；返回 True 表示该事件已被按钮消费。"""
        if not self.enabled:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.collidepoint(event.pos):
            self.pressed = True
            return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            was_pressed = self.pressed
            self.pressed = False
            if was_pressed and self.rect.collidepoint(event.pos):
                if callable(self.action):
                    self.action()
                return True
            return was_pressed
        return False

    def draw(self, surface, fonts):
        """绘制按钮：底色 + 描边 + 居中文字。"""
        if self.enabled:
            fill = self.hover_color if self.hovered else self.base_color
            border = COLOR_ACCENT if self.hovered else self.border_color
            text_color = self.text_color
            if self.pressed:
                fill = tuple(min(255, channel + 18) for channel in fill)
        else:
            fill, border, text_color = DISABLED_FILL, DISABLED_BORDER, COLOR_TEXT_DIM

        pygame.draw.rect(surface, fill, self.rect, border_radius=14)
        pygame.draw.rect(surface, border, self.rect, width=2, border_radius=14)
        image = fonts.get(self.font_size).render(self.text, True, text_color)
        surface.blit(image, image.get_rect(center=self.rect.center))
