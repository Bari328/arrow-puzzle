# -*- coding: utf-8 -*-
"""一键运行全部自检脚本，并汇总结果。

用法（在项目根目录执行）：
    python tests/run_all.py
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPTS = ("check_logic.py", "check_layout.py", "check_render.py")


def main():
    """依次运行三个自检脚本，任一失败则返回非零退出码。"""
    env = dict(os.environ)
    # 自检不需要真实窗口与音频设备
    env.setdefault("SDL_VIDEODRIVER", "dummy")
    env.setdefault("SDL_AUDIODRIVER", "dummy")
    env.setdefault("PYTHONIOENCODING", "utf-8")

    summary = []
    for name in SCRIPTS:
        path = os.path.join(HERE, name)
        print("\n" + "=" * 70)
        print(f"运行 tests/{name}")
        print("=" * 70)
        result = subprocess.run([sys.executable, path], cwd=ROOT, env=env)
        summary.append((name, result.returncode == 0))

    print("\n" + "=" * 70)
    print("汇总")
    print("=" * 70)
    for name, passed in summary:
        print(f"  {'通过' if passed else '失败'}  tests/{name}")
    failed = [name for name, passed in summary if not passed]
    if failed:
        print(f"\n共有 {len(failed)} 个脚本失败：{failed}")
        return 1
    print("\n全部自检通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
