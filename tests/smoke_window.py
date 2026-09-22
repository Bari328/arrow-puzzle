# -*- coding: utf-8 -*-
"""真实显示驱动的冒烟测试：开一个真窗口跑约 2 秒，确认环境能正常起窗与渲染。"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # 仓库根目录（tests 的上一级）
sys.path.insert(0, ROOT)

import pygame

from game.app import App


def main():
    app = App(seed=4)
    driver = pygame.display.get_driver()
    results = []
    for phase, seconds in (("开始界面（飘动箭头 + 实时演示）", 1.5), ("游戏界面", 1.5)):
        if phase == "游戏界面":
            app.start_new_game()
        deadline = time.time() + seconds
        frames = 0
        while time.time() < deadline and app.running:
            app.handle_events()
            app.update(1 / 60)
            app.draw()
            pygame.display.flip()
            app.clock.tick(60)
            frames += 1
        results.append(f"{phase}：{frames / seconds:.0f} FPS")
    print(f"真实窗口（显示驱动 = {driver}，音效就绪 = {app.audio.ready}）")
    for line in results:
        print("  " + line)
    print(f"  当前关卡 = 第 {app.level_index} 关，剩余箭头 = {app.board.remaining}，"
          f"失误剩余 = {app.mistakes_left}")
    pygame.quit()


if __name__ == "__main__":
    main()
