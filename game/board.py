# -*- coding: utf-8 -*-
"""棋盘数据模型。

职责（纯逻辑，不依赖 pygame）：
1. 保存二维网格（0=空，1=上，2=下，3=左，4=右）；
2. 判定某个箭头能否沿自己的方向径直飞出棋盘；
3. 返回点击结果，交给主程序决定"飞出"还是"碰撞"。
"""

from collections import namedtuple

from .config import DIRECTION_VECTORS, DOWN, EMPTY, LEFT, RIGHT, UP

# 点击结果：
#   kind = "empty"   点到空格，什么也不发生
#   kind = "fly"     路径畅通，箭头可以飞出
#   kind = "blocked" 路上有其它箭头挡着
# blocker 为阻挡箭头的坐标 (row, col)，仅在 kind == "blocked" 时有效
ClickResult = namedtuple("ClickResult", "kind row col blocker")


def check_block(grid, row, col, direction, rows, cols):
    """检查指定位置的箭头是否被阻挡。

    参数：
        grid      二维数组，0=空，1=上，2=下，3=左，4=右
        row, col  要检查的箭头所在行列
        direction 方向（1 上 / 2 下 / 3 左 / 4 右）
        rows, cols 棋盘总行数、总列数

    规则：
        从当前格的下一格开始，沿箭头方向一路遍历到边界；
        只要遇到非 0 的格子就说明有箭头挡着，返回 True；
        一直走到边界都是空的，返回 False。

    边界处理：
        - 起点越界、空格、未知方向都返回 False（不会抛异常）；
        - rows / cols 传得比实际大时按实际数组尺寸收敛，避免数组越界；
        - 兼容参差不齐的二维数组（按最短行取列数）。
    """
    # ---- 先做一次防御性校验，保证下面四个分支可以放心索引 ----
    if not grid:
        return False
    height = len(grid)
    width = min((len(line) for line in grid), default=0)
    rows = min(max(int(rows), 0), height)          # rows 传错也不会越界
    cols = min(max(int(cols), 0), width)           # cols 传错也不会越界
    if not (0 <= row < rows and 0 <= col < cols):  # 起点落在棋盘外
        return False

    # ---- 四个方向分别实现，起点自身不参与判断（箭头不会挡住自己）----
    if direction == UP:
        r = row - 1                                # 从当前格的上一格开始
        while r >= 0:
            if grid[r][col] != EMPTY:
                return True                        # 上面有箭头挡着
            r -= 1
        return False                               # 一路到上边界都是空的

    if direction == DOWN:
        r = row + 1                                # 从当前格的下一格开始
        while r < rows:
            if grid[r][col] != EMPTY:
                return True
            r += 1
        return False

    if direction == LEFT:
        c = col - 1                                # 从当前格的左侧一格开始
        while c >= 0:
            if grid[row][c] != EMPTY:
                return True
            c -= 1
        return False

    if direction == RIGHT:
        c = col + 1                                # 从当前格的右侧一格开始
        while c < cols:
            if grid[row][c] != EMPTY:
                return True
            c += 1
        return False

    return False                                   # 未知方向：按"没有阻挡"处理


def path_is_clear(grid, row, col, direction):
    """判断 (row, col) 沿 direction 到棋盘边界之间是否全为空。

    内部复用 check_block()，保证"关卡生成"和"点击判定"用同一份规则，
    这也是"生成的题一定可解"的基础。
    """
    rows = len(grid)
    cols = min((len(line) for line in grid), default=0)
    return not check_block(grid, row, col, direction, rows, cols)


class Board:
    """二维箭头棋盘。"""

    def __init__(self, rows, cols, grid=None):
        self.rows = rows
        self.cols = cols
        if grid is None:
            self.grid = [[EMPTY] * cols for _ in range(rows)]
        else:
            self.grid = [list(row) for row in grid]

    # ------------------------- 构造与快照 -------------------------
    @classmethod
    def from_grid(cls, grid):
        """由二维列表创建棋盘。"""
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        return cls(rows, cols, grid)

    def clone(self):
        """返回内容相同的副本（用于可解性模拟，不影响当前棋盘）。"""
        return Board(self.rows, self.cols, self.grid)

    def snapshot(self):
        """导出快照，"重新开始本关"时用它还原初始局面。"""
        return [list(row) for row in self.grid]

    def restore(self, snapshot):
        """用快照覆盖当前棋盘。"""
        self.grid = [list(row) for row in snapshot]

    # ------------------------- 基础读写 -------------------------
    def in_bounds(self, row, col):
        """坐标是否落在棋盘内。"""
        return 0 <= row < self.rows and 0 <= col < self.cols

    def get(self, row, col):
        """读取格子取值，越界视为空。"""
        if not self.in_bounds(row, col):
            return EMPTY
        return self.grid[row][col]

    def set(self, row, col, value):
        """写入格子取值，越界忽略。"""
        if self.in_bounds(row, col):
            self.grid[row][col] = value

    def is_arrow(self, row, col):
        """该格是否放着箭头。"""
        return self.get(row, col) != EMPTY

    # ------------------------- 统计信息 -------------------------
    @property
    def remaining(self):
        """棋盘上剩余的箭头数量。"""
        return sum(1 for line in self.grid for value in line if value != EMPTY)

    def arrow_positions(self):
        """列出所有箭头的坐标。"""
        return [(r, c)
                for r in range(self.rows)
                for c in range(self.cols)
                if self.grid[r][c] != EMPTY]

    def front_cells(self, row, col):
        """列出该箭头前方直到边界的格子坐标（不含自身）。"""
        direction = self.get(row, col)
        if direction == EMPTY:
            return []
        d_row, d_col = DIRECTION_VECTORS[direction]
        cells = []
        r, c = row + d_row, col + d_col
        while self.in_bounds(r, c):
            cells.append((r, c))
            r += d_row
            c += d_col
        return cells

    # ------------------------- 核心规则 -------------------------
    def blocker_of(self, row, col):
        """返回第一个挡住该箭头的箭头坐标；路径畅通则返回 None。"""
        for r, c in self.front_cells(row, col):
            if self.grid[r][c] != EMPTY:
                return (r, c)
        return None

    def can_fly(self, row, col):
        """该箭头能否径直飞出棋盘（规则完全等价于 check_block 取反）。"""
        return self.is_arrow(row, col) and not self.is_blocked(row, col)

    def is_blocked(self, row, col):
        """该箭头是否被其它箭头挡住（复用模块级 check_block）。"""
        direction = self.get(row, col)
        if direction == EMPTY:
            return False
        return check_block(self.grid, row, col, direction, self.rows, self.cols)

    def click(self, row, col):
        """处理一次点击：只做判定，不修改棋盘。"""
        if self.get(row, col) == EMPTY:
            return ClickResult("empty", row, col, None)
        blocker = self.blocker_of(row, col)
        if blocker is None:
            return ClickResult("fly", row, col, None)
        return ClickResult("blocked", row, col, blocker)

    def remove(self, row, col):
        """移除箭头（飞出之后调用）。"""
        self.set(row, col, EMPTY)

    def free_arrows(self):
        """返回当前所有可以飞出的箭头坐标。"""
        return [pos for pos in self.arrow_positions() if self.can_fly(*pos)]
