# -*- coding: utf-8 -*-
"""像素级渲染自检：确认箭头、辅助线、碰撞反馈、飞出动画都真的画到了画面上。"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # 仓库根目录（tests 的上一级）
sys.path.insert(0, ROOT)

import pygame

from game import renderer
from game.animation import ShakeManager
from game.app import App
from game.board import Board
from game.config import (
    ARROW_COLORS,
    AUDIO_MASTER_VOLUME,
    AUDIO_VOLUMES,
    DIRECTION_VECTORS,
    MENU_PARTICLE_COUNT,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)
from game.effects import Effects

FAILURES = []


def check(condition, message):
    """记录一条断言结果。"""
    if condition:
        print(f"  [OK]   {message}")
    else:
        print(f"  [FAIL] {message}")
        FAILURES.append(message)


def count_near(surface, color, tolerance=26, rect=None):
    """统计画面中与给定颜色接近的像素数量。"""
    rect = rect or pygame.Rect(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT)
    hits = 0
    for x in range(rect.left, rect.right):
        for y in range(rect.top, rect.bottom):
            pixel = surface.get_at((x, y))
            if (abs(pixel.r - color[0]) <= tolerance
                    and abs(pixel.g - color[1]) <= tolerance
                    and abs(pixel.b - color[2]) <= tolerance):
                hits += 1
    return hits


def ink_center(surface, color, rect, tolerance=40):
    """返回矩形内与指定颜色接近的像素的重心，没有匹配像素时返回 None。"""
    count = 0
    sum_x = 0
    sum_y = 0
    for x in range(rect.left, rect.right):
        for y in range(rect.top, rect.bottom):
            pixel = surface.get_at((x, y))
            if (abs(pixel.r - color[0]) <= tolerance
                    and abs(pixel.g - color[1]) <= tolerance
                    and abs(pixel.b - color[2]) <= tolerance):
                count += 1
                sum_x += x
                sum_y += y
    if not count:
        return None
    return (sum_x / count, sum_y / count)


def test_arrows_drawn(app):
    """四种方向的箭头都应出现在画面上。"""
    print("\n[1] 箭头绘制")
    app.load_level(7)
    app.hover_cell = None
    app.draw()
    present = {app.board.get(r, c) for r, c in app.board.arrow_positions()}
    for direction in sorted(present):
        hits = count_near(app.screen, ARROW_COLORS[direction])
        check(hits > 200, f"{renderer.direction_name(direction)}箭头像素数 {hits}")
    board_pixels = count_near(app.screen, (40, 45, 68))
    check(board_pixels > 5000, f"棋盘格子底色像素数 {board_pixels}")


def test_hover_hint(app):
    """悬停时：畅通画绿色路径，被挡画红色路径并给阻挡者描边。"""
    print("\n[2] 悬停辅助线")
    app.load_level(7)
    free = app.board.free_arrows()
    blocked = [pos for pos in app.board.arrow_positions() if not app.board.can_fly(*pos)]
    app.hover_cell = free[0]
    app.draw()
    row, col = free[0]
    center = app.layout.cell_rect(row, col).center
    d_row, d_col = DIRECTION_VECTORS[app.board.get(row, col)]
    # 沿箭头方向在多个距离上采样，只要有一处偏绿就说明路径画出来了
    samples = []
    for ratio in (0.35, 0.7, 1.0, 1.3):
        point = (center[0] + int(d_col * app.layout.cell * ratio),
                 center[1] + int(d_row * app.layout.cell * ratio))
        if (0 <= point[0] < WINDOW_WIDTH) and (0 <= point[1] < WINDOW_HEIGHT):
            samples.append(tuple(app.screen.get_at(point))[:3])
    greenish = [rgb for rgb in samples if rgb[1] > rgb[0] + 10]
    check(bool(greenish), f"畅通路径为绿色（采样点 {samples}）")
    if blocked:
        app.hover_cell = blocked[0]
        app.draw()
        row, col = blocked[0]
        blocker = app.board.blocker_of(row, col)
        start = app.layout.cell_rect(row, col).center
        end = app.layout.cell_rect(*blocker).center
        mid = ((start[0] + end[0]) // 2, (start[1] + end[1]) // 2)
        pixel = app.screen.get_at(mid)
        check(pixel.r > pixel.g + 30, f"被挡路径为红色（采样点 RGB={tuple(pixel)[:3]}）")
        outline = app.layout.cell_rect(*blocker).inflate(16, 16)
        orange = count_near(app.screen, (255, 140, 72), tolerance=45, rect=outline)
        check(orange > 50, f"阻挡者被橙色描边（橙色像素 {orange}）")


def test_collision_feedback(app):
    """点错箭时应有红色碰撞框与红色提示文字。"""
    print("\n[3] 碰撞反馈")
    app.load_level(7)
    app.hover_cell = None
    blocked = [pos for pos in app.board.arrow_positions() if not app.board.can_fly(*pos)]
    if not blocked:
        check(False, "第 7 关没有可用于测试的阻挡情况")
        return
    row, col = blocked[0]
    rect = app.layout.cell_rect(row, col)
    app.handle_board_click(rect.center)
    app.update(0.05)
    app.draw()
    edge = count_near(app.screen, (242, 88, 96), tolerance=45, rect=rect.inflate(10, 10))
    check(edge > 60, f"被点箭头出现红色碰撞框（红色像素 {edge}）")
    toast_rect = pygame.Rect(0, 0, 520, 44)
    toast_rect.center = rect.center
    red_text = count_near(app.screen, (242, 88, 96), tolerance=80, rect=toast_rect)
    check(red_text > 30, f"出现红色提示文字（像素 {red_text}）")


def test_flying_fade(app):
    """飞出动画应带淡出：中途的箭头透明度介于 0 与 255 之间。"""
    print("\n[4] 飞出动画")
    app.load_level(7)
    free = app.board.free_arrows()
    row, col = free[0]
    rect = app.layout.cell_rect(row, col)
    app.handle_board_click(rect.center)
    check(len(app.effects.flyers) == 1, "点击畅通箭头后产生一条飞出动画")
    check(app.board.remaining == app.arrow_total - 1, "飞出后箭头从棋盘上消失")
    flyer = app.effects.flyers[0]
    flyer.update(0.2)
    layer = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
    flyer.draw(layer)
    peak = max(layer.get_at((x, y)).a
               for x in range(0, WINDOW_WIDTH, 3) for y in range(0, WINDOW_HEIGHT, 3))
    check(0 < peak < 255, f"飞行中的箭头被淡出（最高透明度 {peak}）")
    check(flyer.alive, "动画在时长内保持存活")
    flyer.update(1.0)
    check(not flyer.alive, "超过时长后动画结束")


def test_shake_offset(app):
    """确认绘制函数真的按"晃动坐标 + 起始帧"把箭头左右挪了位置。"""
    print("\n[5] 晃动偏移绘制")
    board = Board.from_grid([[4]])               # 单格棋盘：一个朝右的箭头，避免邻格干扰
    layout = renderer.Layout(1, 1)
    empty_effects = Effects()
    shake = ShakeManager()
    region = layout.cell_rect(0, 0).inflate(24, 24)

    app.screen.blit(renderer.make_background(), (0, 0))
    renderer.draw_board(app.screen, app.fonts, layout, board, empty_effects,
                        None, False, shake, 0)
    baseline = ink_center(app.screen, ARROW_COLORS[4], region)
    check(baseline is not None, f"静态箭头重心可测（{baseline}）")

    animation = shake.start((0, 0), 100)
    frames = range(100, 100 + animation.frames)
    best_frame = max(frames, key=lambda frame: abs(shake.offset((0, 0), frame)[0]))
    offset = shake.offset((0, 0), best_frame)[0]
    app.screen.blit(renderer.make_background(), (0, 0))
    renderer.draw_board(app.screen, app.fonts, layout, board, empty_effects,
                        None, False, shake, best_frame)
    moved = ink_center(app.screen, ARROW_COLORS[4], region)
    check(moved is not None, f"晃动帧的箭头重心可测（{moved}）")
    if baseline and moved:
        dx = moved[0] - baseline[0]
        dy = moved[1] - baseline[1]
        check(abs(dx) >= 3, f"箭头横向移动了 {dx:.1f}px（计算出的偏移 {offset:.1f}px）")
        check((dx > 0) == (offset > 0), "移动方向与偏移量的正负一致")
        check(abs(dy) <= 1.0, f"箭头纵向没有位移（{dy:.1f}px）")


def test_menu_screen(app):
    """开始界面：背景飘动箭头、实时演示棋盘、音效胶囊按钮都画出来了。"""
    print("\n[6] 开始界面画面")
    app.state = App.STATE_MENU
    app.draw()
    check(len(app.menu_scene.arrows) == MENU_PARTICLE_COUNT,
          f"背景有 {MENU_PARTICLE_COUNT} 支飘动箭头")
    before = [(round(a.x, 2), round(a.y, 2)) for a in app.menu_scene.arrows]
    for _ in range(30):
        app.update(1 / 60)
    after = [(round(a.x, 2), round(a.y, 2)) for a in app.menu_scene.arrows]
    check(before != after, "装饰箭头在缓慢飘动")
    margin = 90
    check(all(-margin <= x <= WINDOW_WIDTH + margin and -margin <= y <= WINDOW_HEIGHT + margin
              for x, y in after), "飘动箭头出界后从对面绕回，不会飞丢")

    grid_before = [row[:] for row in app.menu_scene.demo.grid]
    for _ in range(60):
        app.update(1 / 60)
    check(grid_before != app.menu_scene.demo.grid, "演示棋盘自动射箭并补位")
    check(len(app.menu_scene.demo.free_arrows()) > 0,
          f"演示棋盘始终留有可飞出的箭（{len(app.menu_scene.demo.free_arrows())} 支）")

    app.draw()
    present = {value for row in app.menu_scene.demo.grid for value in row if value}
    for direction in sorted(present)[:3]:
        hits = count_near(app.screen, ARROW_COLORS[direction], tolerance=16)
        check(hits > 100, f"开始界面能测到{renderer.direction_name(direction)}箭头像素 {hits}")
    glow = count_near(app.screen, (255, 197, 88), tolerance=40,
                      rect=pygame.Rect(WINDOW_WIDTH // 2 - 320, 20, 640, 180))
    check(glow > 800, f"标题发光与装饰元素已绘制（暖色像素 {glow}）")
    chip = app.menu_buttons[3].rect
    check(chip.right <= WINDOW_WIDTH - 80 and chip.top < 100,
          f"音效胶囊按钮贴在右上角 {tuple(chip)}")
    check(app.menu_buttons[3].text.startswith("音效"), f"按钮文案：{app.menu_buttons[3].text}")


def test_audio(app):
    """音效：全部由代码合成、可播放、可静音，且工程里没有音频素材文件。"""
    print("\n[7] 音效")
    mixer = pygame.mixer.get_init()
    check(app.audio.ready, f"混音器就绪：{mixer}（按设备实际采样率/声道数合成）")
    check(mixer is not None and mixer[1] == -16, "采样格式为 16bit 有符号")
    expected = {"shoot", "block", "clear", "fail", "click", "hover", "start"}
    check(expected <= set(app.audio.sounds), f"合成出全部音效：{sorted(app.audio.sounds)}")
    channel = app.audio.play("shoot")
    check(channel is not None, "shoot 音效可以播放（返回播放通道）")
    raw = app.audio.sounds["shoot"].get_raw()
    expect_bytes = int(0.18 * app.audio.sample_rate) * 2 * app.audio.channels
    check(abs(len(raw) - expect_bytes) < 16,
          f"波形长度 {len(raw)} 字节 = 0.18 秒 @ {app.audio.sample_rate}Hz"
          f" x {app.audio.channels} 声道（时长与音高不会走样）")
    check(any(raw), "波形里存在非零采样，不是静音")
    volume = app.audio.sounds["block"].get_volume()
    check(abs(volume - AUDIO_MASTER_VOLUME * AUDIO_VOLUMES["block"]) < 0.01,
          f"音量按配置缩放（block 音量为 {volume:.2f}）")

    app.handle_key(pygame.K_m)
    check(not app.audio.on, "按 M 关闭音效")
    check(app.audio.play("shoot") is None, "静音后 play() 静默跳过")
    app.handle_key(pygame.K_m)
    check(app.audio.on, "再按 M 重新开启音效")

    media = [name for name in os.listdir(os.path.join(ROOT, "game"))
             if name.lower().endswith((".wav", ".mp3", ".ogg", ".flac", ".png", ".jpg"))]
    check(not media, f"game 目录里没有任何音频/图片素材文件（{media}）")


def test_main_loop(app):
    """用真实事件队列与主循环跑若干帧，确认没有异常且状态能推进。"""
    print("\n[8] 主循环冒烟测试")
    app.state = App.STATE_MENU
    frames = 0
    error = None
    try:
        while frames < 300 and app.running:
            frames += 1
            if app.state == App.STATE_MENU:
                pos = app.menu_buttons[0].rect.center      # 点在"开始游戏"按钮上
                pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": pos, "button": 1}))
                pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONUP, {"pos": pos, "button": 1}))
            elif app.state == App.STATE_PLAY:
                free = app.board.free_arrows()
                if free:
                    pos = app.layout.cell_rect(*free[0]).center
                    pygame.event.post(pygame.event.Event(
                        pygame.MOUSEMOTION, {"pos": pos, "rel": (0, 0), "buttons": (0, 0, 0)}))
                    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": pos, "button": 1}))
                    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONUP, {"pos": pos, "button": 1}))
            elif app.state == App.STATE_CLEAR:
                app.auto_next_timer = 0.01
            app.handle_events()
            app.update(1 / 60)
            app.draw()
            pygame.display.flip()
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
    check(error is None, f"连续运行 {frames} 帧无异常（{error}）")
    check(app.best_level >= 2, f"主循环内自动推进了多关（最高第 {app.best_level} 关）")
    check(app.state in (App.STATE_PLAY, App.STATE_CLEAR), "结束时仍处于可玩状态")


if __name__ == "__main__":
    application = App(seed=21)
    test_arrows_drawn(application)
    test_hover_hint(application)
    test_collision_feedback(application)
    test_flying_fade(application)
    test_shake_offset(application)
    test_menu_screen(application)
    test_audio(application)
    test_main_loop(application)
    pygame.quit()
    print("\n" + "=" * 60)
    if FAILURES:
        print(f"共 {len(FAILURES)} 项失败")
        for item in FAILURES:
            print("  -", item)
        sys.exit(1)
    print("渲染自检全部通过")
