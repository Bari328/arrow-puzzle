# -*- coding: utf-8 -*-
"""绘制模块：字体加载、棋盘布局与四个界面的画面。

界面共四个：开始界面 / 游戏界面 / 通关界面 / 失败界面。
所有图形都用 pygame 图元或字体字符绘制，不依赖任何外部图片素材。

每个 draw_xxx 除了画画面，还会返回一张"元素矩形表"（名字 -> Rect），
既方便后续微调排版，也方便用自动化脚本检查元素是否互相压字。
"""

import os
from collections import namedtuple

import pygame

from .config import (
    ARROW_COLORS,
    BOTTOM_HINT_Y,
    COLOR_ACCENT,
    COLOR_BG_BOTTOM,
    COLOR_BG_TOP,
    COLOR_BLOCKER,
    COLOR_BORDER,
    COLOR_CELL,
    COLOR_CELL_HOVER,
    COLOR_DANGER,
    COLOR_PANEL,
    COLOR_PANEL_SOFT,
    COLOR_SUCCESS,
    COLOR_TEXT,
    COLOR_TEXT_DIM,
    DIRECTION_ANGLE,
    DIRECTION_GLYPHS,
    DIRECTION_NAMES,
    DIRECTION_VECTORS,
    EMPTY,
    GRID_MARGIN_BOTTOM,
    GRID_MARGIN_SIDE,
    GRID_MARGIN_TOP,
    HUD_PANEL_BOTTOM,
    HUD_PANEL_HEIGHT,
    HUD_PANEL_TOP,
    POPUP_HEIGHT,
    POPUP_TOP,
    POPUP_WIDTH,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)

# 顶部信息条所需的数据（由 app.py 组装）
Hud = namedtuple("Hud", "level arrow_total arrow_left mistakes_left mistakes_total score")

# 固定位置的几块面板，绘制与排版自检共用
HUD_PANEL = pygame.Rect(GRID_MARGIN_SIDE - 24, HUD_PANEL_TOP,
                        WINDOW_WIDTH - 2 * (GRID_MARGIN_SIDE - 24), HUD_PANEL_HEIGHT)
POPUP_PANEL = pygame.Rect((WINDOW_WIDTH - POPUP_WIDTH) // 2, POPUP_TOP,
                          POPUP_WIDTH, POPUP_HEIGHT)

# 开始界面版式（app.py 里的按钮也按这些常量摆放，保证绘制与自检一致）
MENU_TITLE_Y = 92                 # 标题中心
MENU_SUBTITLE_Y = 150             # 副标题中心
MENU_ORNAMENT_Y = 182             # 装饰下划线
MENU_CARD_TOP = 210               # 两张大卡片的顶部
MENU_CARD_WIDTH = 408
MENU_CARD_HEIGHT = 250
MENU_CARD_MARGIN = 92
MENU_RULE_CARD = pygame.Rect(MENU_CARD_MARGIN, MENU_CARD_TOP,
                             MENU_CARD_WIDTH, MENU_CARD_HEIGHT)
MENU_DEMO_CARD = pygame.Rect(WINDOW_WIDTH - MENU_CARD_MARGIN - MENU_CARD_WIDTH,
                             MENU_CARD_TOP, MENU_CARD_WIDTH, MENU_CARD_HEIGHT)
MENU_SOUND_CHIP = pygame.Rect(WINDOW_WIDTH - MENU_CARD_MARGIN - 176, 24, 176, 38)
MENU_BUTTON_ROW_Y = 486           # 三个主按钮所在行
MENU_BUTTON_SIZE = (240, 56)
MENU_BUTTON_GAP = 24
MENU_STATS_Y = 578
MENU_FOOTER_Y = 620
MENU_TIP_Y = 656

# ---------------------------------------------------------------------------
# 字体加载
# ---------------------------------------------------------------------------
# 常见中文字体：优先按文件路径查找，其次按系统字体名匹配
CJK_FONT_FILES = (
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
    r"C:\Windows\Fonts\Deng.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/System/Library/Fonts/PingFang.ttc",
)
CJK_FONT_NAMES = (
    "microsoftyaheiui", "microsoftyahei", "simhei", "simsun", "dengxian",
    "notosanscjksc", "sourcehansanssc", "wenquanyizenhei", "pingfangsc",
    "arialunicodems",
)

ARROW_CHARS = "↑↓←→"


def resolve_font_path():
    """找到一款能显示中文的字体文件，找不到则返回 None。"""
    for path in CJK_FONT_FILES:
        if os.path.exists(path):
            return path
    for name in CJK_FONT_NAMES:
        matched = pygame.font.match_font(name)
        if matched:
            return matched
    return None


class Fonts:
    """字体管理器：按字号缓存字体对象，避免每帧重复加载。"""

    def __init__(self):
        self.path = resolve_font_path()
        self._cache = {}
        self.title = self.get(66, bold=True)
        self.heading = self.get(40, bold=True)
        self.body = self.get(24)
        self.small = self.get(20)
        self.tiny = self.get(17)
        # 检查字体是否包含箭头字符；不支持时改用多边形绘制箭头
        probe = self.get(48)
        self.glyphs_ok = all(probe.metrics(char)[0] is not None for char in ARROW_CHARS)

    def get(self, size, bold=False):
        """取指定字号的字体对象（带缓存）。"""
        key = (size, bold)
        if key not in self._cache:
            font = None
            if self.path:
                try:
                    font = pygame.font.Font(self.path, size)
                    font.set_bold(bold)
                except (OSError, pygame.error):
                    font = None
            if font is None:
                font = pygame.font.SysFont(None, size, bold=bold)
            self._cache[key] = font
        return self._cache[key]


# ---------------------------------------------------------------------------
# 背景与箭头绘制
# ---------------------------------------------------------------------------
_background_cache = None


def make_background():
    """生成并缓存一张竖向渐变背景，避免每帧重画。"""
    global _background_cache
    if _background_cache is None:
        surface = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
        for y in range(WINDOW_HEIGHT):
            ratio = y / max(WINDOW_HEIGHT - 1, 1)
            color = tuple(int(COLOR_BG_TOP[i] + (COLOR_BG_BOTTOM[i] - COLOR_BG_TOP[i]) * ratio)
                          for i in range(3))
            pygame.draw.line(surface, color, (0, y), (WINDOW_WIDTH, y))
        _background_cache = surface
    return _background_cache


def arrow_polygon_surface(direction, size, color):
    """字体不支持箭头字符时的兜底方案：用多边形画箭头再旋转到目标方向。"""
    size = max(size, 12)
    surface = pygame.Surface((size, size), pygame.SRCALPHA)
    points = [
        (size * 0.50, size * 0.06),   # 箭头尖
        (size * 0.94, size * 0.52),   # 右侧翼
        (size * 0.66, size * 0.52),
        (size * 0.66, size * 0.94),   # 箭杆右下
        (size * 0.34, size * 0.94),   # 箭杆左下
        (size * 0.34, size * 0.52),
        (size * 0.06, size * 0.52),   # 左侧翼
    ]
    pygame.draw.polygon(surface, color, points)
    return pygame.transform.rotate(surface, DIRECTION_ANGLE[direction])


_arrow_cache = {}


def make_arrow_image(fonts, direction, cell_size, color, scale=1.0):
    """按格子尺寸生成箭头图像（字符优先，多边形兜底），结果带缓存。

    开始界面有几十支装饰箭头、棋盘上也有几十支，缓存后每帧只做贴图，
    不再重复渲染字符。
    """
    size = int(cell_size * 0.66 * scale)
    key = (id(fonts), direction, size, tuple(color))
    image = _arrow_cache.get(key)
    if image is not None:
        return image
    if fonts.glyphs_ok:
        image = fonts.get(size, bold=True).render(DIRECTION_GLYPHS[direction], True, color)
    else:
        image = arrow_polygon_surface(direction, size, color)
    _arrow_cache[key] = image
    return image


def draw_arrow(surface, fonts, center, direction, color, cell_size, scale=1.0):
    """在指定位置绘制箭头（字符带一层淡投影，看起来更立体）。"""
    image = make_arrow_image(fonts, direction, cell_size, color, scale)
    if fonts.glyphs_ok:
        shadow = make_arrow_image(fonts, direction, cell_size, (16, 18, 30), scale)
        surface.blit(shadow, shadow.get_rect(center=(center[0] + 1, center[1] + 3)))
    surface.blit(image, image.get_rect(center=(int(center[0]), int(center[1]))))


# ---------------------------------------------------------------------------
# 棋盘布局
# ---------------------------------------------------------------------------
class Layout:
    """棋盘布局：把棋盘居中摆放，并算出每格的矩形。"""

    def __init__(self, rows, cols):
        self.rows = rows
        self.cols = cols
        available_w = WINDOW_WIDTH - 2 * GRID_MARGIN_SIDE
        available_h = WINDOW_HEIGHT - GRID_MARGIN_TOP - GRID_MARGIN_BOTTOM
        self.cell = int(min(available_w / cols, available_h / rows))
        self.cell = max(38, min(self.cell, 96))          # 限制格子大小，保证观感
        self.board_width = self.cell * cols
        self.board_height = self.cell * rows
        self.origin_x = (WINDOW_WIDTH - self.board_width) // 2
        self.origin_y = GRID_MARGIN_TOP + (available_h - self.board_height) // 2
        self.board_rect = pygame.Rect(self.origin_x, self.origin_y,
                                      self.board_width, self.board_height)
        # 棋盘底板（含外框）
        self.frame_rect = self.board_rect.inflate(26, 26)
        # 飞出动画的裁剪范围：横向允许飞出棋盘，纵向不越过顶部信息条
        allowed = pygame.Rect(0, HUD_PANEL_BOTTOM, WINDOW_WIDTH, WINDOW_HEIGHT - HUD_PANEL_BOTTOM)
        self.clip_rect = self.board_rect.inflate(self.cell * 2, self.cell * 2).clip(allowed)

    def cell_rect(self, row, col):
        """返回某格的矩形。"""
        return pygame.Rect(self.origin_x + col * self.cell,
                           self.origin_y + row * self.cell,
                           self.cell, self.cell)

    def cell_at(self, pos):
        """把屏幕坐标换算成格子坐标，落在棋盘外返回 None。"""
        if not self.board_rect.collidepoint(pos):
            return None
        col = int((pos[0] - self.origin_x) // self.cell)
        row = int((pos[1] - self.origin_y) // self.cell)
        if 0 <= row < self.rows and 0 <= col < self.cols:
            return (row, col)
        return None


# ---------------------------------------------------------------------------
# 游戏界面
# ---------------------------------------------------------------------------
def draw_game(surface, fonts, layout, board, effects, hover_cell, hud,
              show_hint=True, shake=None, frame=0):
    """绘制游戏界面：顶部信息条 + 棋盘 + 箭头 + 特效 + 底部说明。"""
    elements = {}
    surface.blit(make_background(), (0, 0))
    elements.update(draw_top_hud(surface, fonts, hud))
    elements.update(draw_board(surface, fonts, layout, board, effects, hover_cell,
                               show_hint, shake, frame))
    elements["bottom_hint"] = draw_bottom_hint(surface, fonts, show_hint)
    return elements


def draw_top_hud(surface, fonts, hud):
    """顶部信息条：关卡、剩余箭头进度、失误次数、得分。"""
    elements = {"hud_panel": HUD_PANEL}
    pygame.draw.rect(surface, COLOR_PANEL, HUD_PANEL, border_radius=18)
    pygame.draw.rect(surface, COLOR_BORDER, HUD_PANEL, width=2, border_radius=18)

    # ---- 左：关卡 ----
    level_text = fonts.heading.render(f"第 {hud.level} 关", True, COLOR_TEXT)
    elements["level_text"] = level_text.get_rect(topleft=(HUD_PANEL.x + 30, HUD_PANEL.y + 20))
    surface.blit(level_text, elements["level_text"])
    tips = fonts.tiny.render("一箭又一箭 · 点掉所有能飞出去的箭", True, COLOR_TEXT_DIM)
    elements["level_tip"] = tips.get_rect(topleft=(HUD_PANEL.x + 32, HUD_PANEL.y + 76))
    surface.blit(tips, elements["level_tip"])

    # ---- 中：剩余箭头 + 进度条 ----
    cleared = max(hud.arrow_total - hud.arrow_left, 0)
    ratio = cleared / hud.arrow_total if hud.arrow_total else 0.0
    center_x = HUD_PANEL.centerx + 40
    label = fonts.small.render(f"剩余箭头 {hud.arrow_left} / {hud.arrow_total}", True, COLOR_TEXT)
    elements["arrow_label"] = label.get_rect(center=(center_x, HUD_PANEL.y + 36))
    surface.blit(label, elements["arrow_label"])
    bar = pygame.Rect(0, 0, 280, 14)
    bar.center = (center_x, HUD_PANEL.y + 72)
    elements["arrow_bar"] = bar
    pygame.draw.rect(surface, COLOR_PANEL_SOFT, bar, border_radius=7)
    if ratio > 0:
        filled = pygame.Rect(bar.x, bar.y, int(bar.width * ratio), bar.height)
        pygame.draw.rect(surface, COLOR_ACCENT, filled, border_radius=7)
    pygame.draw.rect(surface, COLOR_BORDER, bar, width=1, border_radius=7)
    percent = fonts.tiny.render(f"已清空 {int(ratio * 100)}%", True, COLOR_TEXT_DIM)
    elements["arrow_percent"] = percent.get_rect(center=(center_x, HUD_PANEL.y + 98))
    surface.blit(percent, elements["arrow_percent"])

    # ---- 右：得分 + 失误机会（圆点）----
    score_text = fonts.body.render(f"得分 {hud.score}", True, COLOR_ACCENT)
    elements["score_text"] = score_text.get_rect(topright=(HUD_PANEL.right - 30, HUD_PANEL.y + 22))
    surface.blit(score_text, elements["score_text"])
    mistake_label = fonts.tiny.render("失误机会", True, COLOR_TEXT_DIM)
    elements["mistake_label"] = mistake_label.get_rect(topright=(HUD_PANEL.right - 30, HUD_PANEL.y + 58))
    surface.blit(mistake_label, elements["mistake_label"])
    dots = []
    for index in range(hud.mistakes_total):
        center = (HUD_PANEL.right - 42 - index * 28, HUD_PANEL.y + 94)
        dots.append(pygame.Rect(center[0] - 9, center[1] - 9, 18, 18))
        if index < hud.mistakes_left:
            pygame.draw.circle(surface, COLOR_DANGER, center, 9)
        else:
            pygame.draw.circle(surface, (72, 78, 104), center, 9, width=2)
    elements["mistake_dots"] = dots[0].unionall(dots[1:]) if dots else pygame.Rect(0, 0, 0, 0)
    return elements


def draw_board(surface, fonts, layout, board, effects, hover_cell,
               show_hint=True, shake=None, frame=0):
    """绘制棋盘底板、格子、悬停辅助线与箭头，最后叠加同层特效。

    被撞箭头的左右晃动在这里应用：偏移量 = shake.offset((row, col), frame)，
    也就是"晃动坐标 + 动画起始帧"两个变量算出来的结果。
    """
    elements = {"board_frame": layout.frame_rect}
    pygame.draw.rect(surface, COLOR_PANEL, layout.frame_rect, border_radius=22)
    pygame.draw.rect(surface, COLOR_BORDER, layout.frame_rect, width=2, border_radius=22)

    # ---- 格子底 ----
    for row in range(board.rows):
        for col in range(board.cols):
            inner = layout.cell_rect(row, col).inflate(-6, -6)
            hovered = hover_cell == (row, col)
            pygame.draw.rect(surface, COLOR_CELL_HOVER if hovered else COLOR_CELL,
                             inner, border_radius=10)
            if hovered:
                pygame.draw.rect(surface, COLOR_BORDER, inner, width=2, border_radius=10)

    # ---- 悬停辅助线：提前告诉玩家这一箭能不能飞出去 ----
    if show_hint and hover_cell is not None and board.is_arrow(*hover_cell):
        draw_path_hint(surface, layout, board, hover_cell)

    # ---- 箭头本体 ----
    for row, col in board.arrow_positions():
        direction = board.get(row, col)
        rect = layout.cell_rect(row, col)
        offset_x, offset_y = shake.offset((row, col), frame) if shake else (0.0, 0.0)
        center = (rect.centerx + offset_x, rect.centery + offset_y)
        scale = 1.08 if hover_cell == (row, col) else 1.0
        draw_arrow(surface, fonts, center, direction, ARROW_COLORS[direction],
                   layout.cell, scale)

    # ---- 与棋盘同层的特效（碰撞框、飞出动画）----
    previous_clip = surface.get_clip()
    surface.set_clip(layout.clip_rect)
    effects.draw_board_layer(surface)
    surface.set_clip(previous_clip)
    return elements


def draw_path_hint(surface, layout, board, cell):
    """绘制悬停箭头的飞行路径：畅通画绿色，被挡画红色并标出阻挡者。"""
    row, col = cell
    direction = board.get(row, col)
    if direction == EMPTY:
        return
    d_row, d_col = DIRECTION_VECTORS[direction]
    center = layout.cell_rect(row, col).center
    blocker = board.blocker_of(row, col)
    overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)

    if d_row:
        steps = (row + 1) if d_row < 0 else (board.rows - row)
    else:
        steps = (col + 1) if d_col < 0 else (board.cols - col)

    if blocker is None:
        # 畅通：一直画到棋盘底板边缘，表示"直接飞出去"
        travel = (steps - 0.5) * layout.cell + 12
        end = (center[0] + d_col * travel, center[1] + d_row * travel)
        line_color = (*COLOR_SUCCESS, 130)
    else:
        # 被挡：只画到阻挡者身上
        end = layout.cell_rect(*blocker).center
        line_color = (*COLOR_DANGER, 150)

    pygame.draw.line(overlay, line_color, center, end, 6)
    pygame.draw.circle(overlay, line_color, end, 7)
    surface.blit(overlay, (0, 0))

    if blocker is not None:
        pygame.draw.rect(surface, COLOR_BLOCKER,
                         layout.cell_rect(*blocker).inflate(-6, -6),
                         width=3, border_radius=10)


def draw_bottom_hint(surface, fonts, show_hint=True):
    """底部操作说明，返回它的矩形。"""
    hint_state = "开" if show_hint else "关"
    text = ("点击箭头即可射出 · 被挡住的箭会消耗一次失误 · "
            f"R 重开本关 · ESC 返回主菜单 · H 辅助线({hint_state})")
    image = fonts.tiny.render(text, True, COLOR_TEXT_DIM)
    rect = image.get_rect(center=(WINDOW_WIDTH // 2, BOTTOM_HINT_Y))
    surface.blit(image, rect)
    return rect


# ---------------------------------------------------------------------------
# 开始界面
# ---------------------------------------------------------------------------
def draw_menu(surface, fonts, best_level, total_score, scene=None):
    """绘制开始界面：发光标题 + 玩法卡片 + 实时演示卡片 + 统计信息。

    scene 传 MenuScene 时，会画出背景飘动箭头与自动射箭的演示小棋盘。
    """
    elements = {}
    surface.blit(make_background(), (0, 0))
    if scene is not None:
        scene.draw_background(surface, fonts)     # 背景飘动箭头
    draw_title_glow(surface)
    elements.update(draw_menu_header(surface, fonts))
    elements.update(draw_menu_cards(surface, fonts, scene))

    stats = f"最高通关：第 {max(best_level, 0)} 关    累计得分：{total_score}"
    image = fonts.small.render(stats, True, COLOR_TEXT_DIM)
    elements["stats"] = image.get_rect(center=(WINDOW_WIDTH // 2, MENU_STATS_Y))
    surface.blit(image, elements["stats"])

    footer = fonts.tiny.render("键盘：空格 开始 / 继续 · R 重开本关 · ESC 返回或退出 · M 开关音效",
                               True, COLOR_TEXT_DIM)
    elements["footer"] = footer.get_rect(center=(WINDOW_WIDTH // 2, MENU_FOOTER_Y))
    surface.blit(footer, elements["footer"])

    tip = fonts.tiny.render("鼠标悬停箭头可预览飞行路径（游戏内按 H 开关辅助线）", True, COLOR_TEXT_DIM)
    elements["tip"] = tip.get_rect(center=(WINDOW_WIDTH // 2, MENU_TIP_Y))
    surface.blit(tip, elements["tip"])
    return elements


def draw_title_glow(surface):
    """标题背后的柔光：叠若干层半透明椭圆，做出中心发光的效果。"""
    glow = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
    for step in range(14, 0, -1):
        rect = pygame.Rect(0, 0, 260 + step * 26, 74 + step * 9)
        rect.center = (WINDOW_WIDTH // 2, MENU_TITLE_Y)
        pygame.draw.ellipse(glow, (*COLOR_ACCENT, 4), rect)
    surface.blit(glow, (0, 0))


def draw_menu_header(surface, fonts):
    """标题区：发光描边的标题 + 副标题 + 两端带箭头的装饰线。"""
    elements = {}
    center_x = WINDOW_WIDTH // 2

    title = fonts.title.render("一箭又一箭", True, COLOR_TEXT)
    rect = title.get_rect(center=(center_x, MENU_TITLE_Y))
    glow = fonts.title.render("一箭又一箭", True, COLOR_ACCENT).copy()
    glow.set_alpha(38)
    for dx, dy in ((-6, 0), (6, 0), (0, -5), (0, 5), (-5, -4), (5, 4), (-5, 4), (5, -4)):
        surface.blit(glow, rect.move(dx, dy))
    surface.blit(fonts.title.render("一箭又一箭", True, (9, 11, 20)), rect.move(2, 5))
    surface.blit(title, rect)
    elements["title"] = rect

    subtitle = fonts.body.render("箭头解谜 · 点掉所有能飞出去的箭", True, COLOR_ACCENT)
    elements["subtitle"] = subtitle.get_rect(center=(center_x, MENU_SUBTITLE_Y))
    surface.blit(subtitle, elements["subtitle"])

    line = pygame.Rect(0, 0, 440, 2)
    line.center = (center_x, MENU_ORNAMENT_Y)
    pygame.draw.rect(surface, COLOR_BORDER, line, border_radius=1)
    pygame.draw.circle(surface, COLOR_ACCENT, line.center, 4)
    boxes = [line]
    if fonts.glyphs_ok:
        for glyph, anchor_x in (("←", line.left - 22), ("→", line.right + 22)):
            image = fonts.get(26, bold=True).render(glyph, True, COLOR_ACCENT)
            rect_glyph = image.get_rect(center=(anchor_x, line.centery))
            surface.blit(image, rect_glyph)
            boxes.append(rect_glyph)
    elements["ornament"] = boxes[0].unionall(boxes[1:])
    return elements


def draw_card(surface, rect, border_color=COLOR_BORDER):
    """卡片底板：深色圆角矩形 + 描边。"""
    pygame.draw.rect(surface, COLOR_PANEL, rect, border_radius=20)
    pygame.draw.rect(surface, border_color, rect, width=2, border_radius=20)


def draw_menu_cards(surface, fonts, scene=None):
    """左侧"怎么玩"卡片 + 右侧"实时演示"卡片，返回卡片内的元素矩形。"""
    elements = {"rule_card": MENU_RULE_CARD, "demo_card": MENU_DEMO_CARD}

    # ---- 左：玩法说明 ----
    draw_card(surface, MENU_RULE_CARD)
    title = fonts.small.render("怎么玩", True, COLOR_TEXT)
    elements["rule_title"] = title.get_rect(x=MENU_RULE_CARD.x + 24, y=MENU_RULE_CARD.y + 20)
    surface.blit(title, elements["rule_title"])
    lines = [
        "① 点击箭头，沿箭头方向看到棋盘边界",
        "② 路上没有其它箭头 → 飞出并消失",
        "③ 有箭头挡着 → 撞停，失误 -1（每关 3 次）",
        "④ 清空全部箭头 → 通关并自动进入下一关",
    ]
    boxes = []
    for index, text in enumerate(lines):
        color = COLOR_TEXT if index < 2 else COLOR_TEXT_DIM
        image = fonts.tiny.render(text, True, color)
        rect = image.get_rect(topleft=(MENU_RULE_CARD.x + 24, MENU_RULE_CARD.y + 62 + index * 30))
        surface.blit(image, rect)
        boxes.append(rect)
    elements["rule_text"] = boxes[0].unionall(boxes[1:])
    note = fonts.tiny.render("提示：颜色只用来区分方向，不代表能不能飞", True, COLOR_ACCENT)
    elements["rule_note"] = note.get_rect(topleft=(MENU_RULE_CARD.x + 24, MENU_RULE_CARD.y + 196))
    surface.blit(note, elements["rule_note"])

    # ---- 右：实时演示（箭头自动飞出并补位）----
    draw_card(surface, MENU_DEMO_CARD)
    demo_title = fonts.small.render("实时演示", True, COLOR_TEXT)
    elements["demo_title"] = demo_title.get_rect(x=MENU_DEMO_CARD.x + 24, y=MENU_DEMO_CARD.y + 20)
    surface.blit(demo_title, elements["demo_title"])
    area = pygame.Rect(MENU_DEMO_CARD.x + 16, MENU_DEMO_CARD.y + 56,
                       MENU_DEMO_CARD.width - 32, 132)
    if scene is not None:
        elements["demo_board"] = scene.draw_demo(surface, fonts, area)
    else:
        elements["demo_board"] = area
    caption = fonts.tiny.render("箭头会自动飞出，再从别处补一支", True, COLOR_TEXT_DIM)
    elements["demo_caption"] = caption.get_rect(center=(MENU_DEMO_CARD.centerx,
                                                        MENU_DEMO_CARD.y + 218))
    surface.blit(caption, elements["demo_caption"])
    return elements


# ---------------------------------------------------------------------------
# 通关界面
# ---------------------------------------------------------------------------
def draw_level_clear(surface, fonts, hud, countdown_ratio, next_level):
    """绘制通关界面：半透明遮罩 + 战绩面板 + 自动进入下一关的倒计时。"""
    elements = {"panel": POPUP_PANEL}
    dim_overlay(surface, (6, 10, 18, 170))
    pygame.draw.rect(surface, COLOR_PANEL, POPUP_PANEL, border_radius=22)
    pygame.draw.rect(surface, COLOR_SUCCESS, POPUP_PANEL, width=3, border_radius=22)

    title = fonts.heading.render(f"第 {hud.level} 关 通关！", True, COLOR_SUCCESS)
    elements["title"] = title.get_rect(center=(POPUP_PANEL.centerx, 254))
    surface.blit(title, elements["title"])

    if hud.mistakes_left == hud.mistakes_total:
        stars = "★ ★ ★"
    elif hud.mistakes_left > 0:
        stars = "★ ★"
    else:
        stars = "★"
    star_image = fonts.heading.render(stars, True, COLOR_ACCENT)
    elements["stars"] = star_image.get_rect(center=(POPUP_PANEL.centerx, 314))
    surface.blit(star_image, elements["stars"])

    lines = [
        f"本关得分：{hud.score}",
        f"剩余失误：{hud.mistakes_left} / {hud.mistakes_total}",
        "全部箭头已清空，漂亮！",
    ]
    boxes = []
    for index, text in enumerate(lines):
        color = COLOR_TEXT if index == 0 else COLOR_TEXT_DIM
        image = fonts.body.render(text, True, color)
        rect = image.get_rect(center=(POPUP_PANEL.centerx, 362 + index * 32))
        surface.blit(image, rect)
        boxes.append(rect)
    elements["stats"] = boxes[0].unionall(boxes[1:])

    # 自动进入下一关的倒计时条
    bar = pygame.Rect(0, 0, 420, 12)
    bar.center = (POPUP_PANEL.centerx, 556)
    elements["countdown_bar"] = bar
    pygame.draw.rect(surface, COLOR_PANEL_SOFT, bar, border_radius=6)
    ratio = max(0.0, min(1.0, countdown_ratio))
    if ratio > 0:
        filled = pygame.Rect(bar.x, bar.y, int(bar.width * ratio), bar.height)
        pygame.draw.rect(surface, COLOR_SUCCESS, filled, border_radius=6)
    countdown = fonts.tiny.render(f"即将自动进入第 {next_level} 关", True, COLOR_TEXT_DIM)
    elements["countdown_text"] = countdown.get_rect(center=(POPUP_PANEL.centerx, 586))
    surface.blit(countdown, elements["countdown_text"])
    return elements


# ---------------------------------------------------------------------------
# 失败界面
# ---------------------------------------------------------------------------
def draw_game_over(surface, fonts, hud):
    """绘制失败界面：半透明遮罩 + 失败信息面板。"""
    elements = {"panel": POPUP_PANEL}
    dim_overlay(surface, (20, 6, 10, 180))
    pygame.draw.rect(surface, COLOR_PANEL, POPUP_PANEL, border_radius=22)
    pygame.draw.rect(surface, COLOR_DANGER, POPUP_PANEL, width=3, border_radius=22)

    title = fonts.heading.render("失误用尽 · 本关失败", True, COLOR_DANGER)
    elements["title"] = title.get_rect(center=(POPUP_PANEL.centerx, 256))
    surface.blit(title, elements["title"])

    lines = [
        f"关卡：第 {hud.level} 关",
        f"剩余箭头：{hud.arrow_left} / {hud.arrow_total}",
        "小提示：先射那些一路到边界的箭，再处理被挡住的。",
        "按 H 开关辅助线，可以直观看清每一箭的路径。",
    ]
    boxes = []
    for index, text in enumerate(lines):
        color = COLOR_TEXT_DIM if index >= 2 else COLOR_TEXT
        image = fonts.small.render(text, True, color)
        rect = image.get_rect(center=(POPUP_PANEL.centerx, 322 + index * 34))
        surface.blit(image, rect)
        boxes.append(rect)
    elements["stats"] = boxes[0].unionall(boxes[1:])
    return elements


def dim_overlay(surface, color):
    """给当前画面压一层半透明遮罩，突出弹窗面板。"""
    overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
    overlay.fill(color)
    surface.blit(overlay, (0, 0))


def direction_name(direction):
    """把方向常量翻译成中文，供提示文字复用。"""
    return DIRECTION_NAMES.get(direction, "未知")
