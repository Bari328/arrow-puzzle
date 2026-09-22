# -*- coding: utf-8 -*-
"""一箭又一箭 · 箭头解谜小游戏 —— 程序入口。

运行方式：
    python main.py

依赖：Python 3.8+ 与 pygame（安装：pip install pygame）
"""

import sys

from game.app import App


def main():
    """创建应用并进入主循环。"""
    app = App()
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
