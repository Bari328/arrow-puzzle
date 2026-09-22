# -*- coding: utf-8 -*-
"""一箭又一箭 · 箭头解谜小游戏（Pygame 实现）。

包内模块分工：
    config.py   全局常量：窗口、配色、方向取值、难度参数
    board.py    棋盘数据模型与"能否飞出"的核心判定规则
    levels.py   关卡生成（逆向构造法）与可解性校验
    effects.py  特效：箭头飞出、碰撞抖动、浮动提示
    ui.py       界面小部件（按钮）
    renderer.py 字体加载、棋盘布局与四个界面的绘制
    app.py      状态机与主循环
"""

__all__ = ["app", "board", "config", "effects", "levels", "renderer", "ui"]
