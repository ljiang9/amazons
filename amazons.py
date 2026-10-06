"""亚马逊棋 (Game of the Amazons) —— 纯标准库实现.

规则:
- 10x10 棋盘, 双方各 4 枚亚马逊(皇后).
- 每回合走一步: 选一枚己方亚马逊, 按皇后走法移到空位,
  然后从新位置按皇后走法射出一箭(箭落地处变成障碍).
- 箭可以射回出发格. 被箭/棋子占据的格不能再进入.
- 一方无合法走法即判负, 另一方获胜.
"""
import argparse
import copy
import random
import sys

SIZE = 10
EMPTY, ARROW = -1, -2
DIRS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

# 经典开局: 白方(0) 第 4 行/第 7 行, 黑方(1) 对称
OPENING = {
    0: [(3, 0), (3, 9), (0, 3), (0, 6)],
    1: [(6, 0), (6, 9), (9, 3), (9, 6)],
}


def new_board():
    b = [[EMPTY] * SIZE for _ in range(SIZE)]
    for p, cells in OPENING.items():
        for r, c in cells:
            b[r][c] = p
    return b


def ray_targets(board, r, c, blocked_extra=None):
    """从 (r,c) 按皇后走法可达的所有空格. blocked_extra: 额外视为障碍的格集合."""
    out = []
    for dr, dc in DIRS:
        nr, nc = r + dr, c + dc
        while 0 <= nr < SIZE and 0 <= nc < SIZE:
            if board[nr][nc] != EMPTY or (blocked_extra and (nr, nc) in blocked_extra):
                break
            out.append((nr, nc))
            nr += dr
            nc += dc
    return out


def amazon_moves(board, player):
    """返回所有合法走法: (fr,fc,tr,tc,ar,ac)."""
    moves = []
    for fr in range(SIZE):
        for fc in range(SIZE):
            if board[fr][fc] != player:
                continue
            # 移动时出发格暂时空出
            board[fr][fc] = EMPTY
            for tr, tc in ray_targets(board, fr, fc):
                # 落子后从新位置射箭, 出发格可被射中
                board[tr][tc] = player
                for ar, ac in ray_targets(board, tr, tc):
                    moves.append((fr, fc, tr, tc, ar, ac))
                board[tr][tc] = EMPTY
            board[fr][fc] = player
    return moves


def apply_move(board, player, move):
    """在棋盘上执行走法, 返回箭落子后该走法是否结束对方全部走法(供检测用)."""
    fr, fc, tr, tc, ar, ac = move
    if board[fr][fc] != player:
        raise ValueError("走法起点不是己方亚马逊")
    if board[tr][tc] != EMPTY and (tr, tc) != (fr, fc):
        raise ValueError("走法落点不为空")
    if board[ar][ac] != EMPTY and (ar, ac) not in ((fr, fc), (tr, tc)):
        raise ValueError("箭落点不为空")
    # 校验走法确实是皇后走法且路径畅通
    def queen_ok(sr, sc, er, ec, allow_end_blocked=False):
        dr, dc = er - sr, ec - sc
        if dr == 0 and dc == 0:
            return False
        if dr != 0 and dc != 0 and abs(dr) != abs(dc):
            return False
        sdr = (dr > 0) - (dr < 0)
        sdc = (dc > 0) - (dc < 0)
        r, c = sr + sdr, sc + sdc
        while (r, c) != (er, ec):
            if board[r][c] != EMPTY and (r, c) != (fr, fc):
                return False
            r += sdr
            c += sdc
        return True
    if not queen_ok(fr, fc, tr, tc):
        raise ValueError("亚马逊移动不符合皇后走法")
    board[fr][fc] = EMPTY
    if not queen_ok(tr, tc, ar, ac):
        board[fr][fc] = player
        raise ValueError("射箭不符合皇后走法")
    board[tr][tc] = player
    board[ar][ac] = ARROW


def mobility(board, player):
    """某方所有亚马逊的皇后可达空格数(粗略领地估计)."""
    n = 0
    for r in range(SIZE):
        for c in range(SIZE):
            if board[r][c] == player:
                board[r][c] = EMPTY
                n += len(ray_targets(board, r, c))
                board[r][c] = player
    return n


def ai_move(board, player, rng):
    """贪心: 最大化 (己方机动 - 对方机动), 平局随机."""
    moves = amazon_moves(board, player)
    if not moves:
        return None
    opp = 1 - player
    scored = []
    for m in moves:
        b2 = copy.deepcopy(board)
        apply_move(b2, player, m)
        score = mobility(b2, player) - mobility(b2, opp)
        scored.append((score, m))
    best = max(s for s, _ in scored)
    cands = [m for s, m in scored if s == best]
    return rng.choice(cands)


def play_auto(games, seed, verbose=False):
    rng = random.Random(seed)
    wins = [0, 0]
    draws = 0
    for gi in range(games):
        board = new_board()
        turn = 0
        plies = 0
        while True:
            mv = ai_move(board, turn, rng)
            if mv is None:
                wins[1 - turn] += 1
                if verbose:
                    print(f"第 {gi+1}/{games} 局: {'黑' if turn else '白'}无棋可走, "
                          f"{'白' if turn else '黑'}胜 ({plies} 半回合)")
                break
            apply_move(board, turn, mv)
            plies += 1
            turn = 1 - turn
    return wins, draws


# ---------- 文本界面 ----------

def parse_sq(s):
    s = s.strip().lower()
    if len(s) < 2 or not s[0].isalpha() or not s[1:].isdigit():
        raise ValueError(f"坐标格式错误: {s}")
    c = ord(s[0]) - ord('a')
    row_n = int(s[1:])
    if not (0 <= c < SIZE and 1 <= row_n <= SIZE):
        raise ValueError(f"坐标越界: {s}")
    return SIZE - row_n, c


def fmt_sq(r, c):
    return f"{chr(ord('a') + c)}{SIZE - r}"


def render(board):
    sym = {EMPTY: '·', ARROW: '✕', 0: '♕', 1: '♛'}
    lines = ["   " + " ".join(chr(ord('a') + c) for c in range(SIZE))]
    for r in range(SIZE):
        lines.append(f"{SIZE - r:2d} " + " ".join(sym[board[r][c]] for c in range(SIZE)))
    return "\n".join(lines)


def play_interactive():
    if not sys.stdin.isatty():
        print("交互模式需要终端; 无头演示请用 --auto", file=sys.stderr)
        sys.exit(2)
    board = new_board()
    turn = 0
    name = ["白方(♕)", "黑方(♛)"]
    print("亚马逊棋: 每回合输入 起点 落点 箭落点, 如: d7 d4 d4")
    print("(箭可射回起点; q 退出)")
    while True:
        print(render(board))
        if not amazon_moves(board, turn):
            print(f"{name[turn]}无棋可走, {name[1-turn]}获胜!")
            return
        try:
            raw = input(f"{name[turn]}走棋> ").strip()
        except EOFError:
            return
        if raw.lower() in ("q", "quit", "退出"):
            return
        parts = raw.split()
        if len(parts) != 3:
            print("请输入三个坐标: 起点 落点 箭落点")
            continue
        try:
            fr, fc = parse_sq(parts[0])
            tr, tc = parse_sq(parts[1])
            ar, ac = parse_sq(parts[2])
            apply_move(board, turn, (fr, fc, tr, tc, ar, ac))
        except ValueError as e:
            print("非法走法:", e)
            continue
        turn = 1 - turn


def main():
    ap = argparse.ArgumentParser(description="亚马逊棋 (Game of the Amazons)")
    ap.add_argument("--auto", action="store_true", help="AI 对 AI 自动演示")
    ap.add_argument("--games", type=int, default=5, help="自动演示局数")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    if args.auto:
        wins, draws = play_auto(args.games, args.seed, args.verbose)
        print(f"自动演示结束: 共 {args.games} 局, 白胜 {wins[0]}, 黑胜 {wins[1]}, 和棋 {draws}")
    else:
        play_interactive()


if __name__ == "__main__":
    main()
