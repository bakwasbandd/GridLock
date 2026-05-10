from dataclasses import dataclass, field
from typing import List, Optional

from .lexer import tokenize


@dataclass
class Program:
    statements: List[object] = field(default_factory=list)


@dataclass
class GridStmt:
    width: int
    height: int
    randomized: bool = False


@dataclass
class EntityStmt:
    kind: str  # 'player','enemy','wall','goal'
    x: int
    y: int
    extra: Optional[dict] = None


@dataclass
class ScoreStmt:
    amount: int
    event: str


@dataclass
class RuleCond:
    left: str
    op: str
    right: str


@dataclass
class RuleStmt:
    cond: RuleCond
    action: str


def parse_line(line: str):
    line = line.strip()
    if not line or line.startswith('#'):
        return None
    try:
        tokens = [tok for tok in tokenize(line) if tok.type != 'NEWLINE']
    except SyntaxError as exc:
        raise SyntaxError(str(exc))

    if not tokens:
        return None

    # rule: header
    if (
        len(tokens) == 2
        and tokens[0].type == 'ID' and tokens[0].value == 'rule'
        and tokens[1].type == 'COLON'
    ):
        return 'RULE_HEADER'

    # grid W H
    if (
        len(tokens) == 3
        and tokens[0].type == 'ID' and tokens[0].value == 'grid'
        and tokens[1].type == 'NUMBER'
        and tokens[2].type == 'NUMBER'
    ):
        return GridStmt(tokens[1].value, tokens[2].value)

    # grid random W H
    if (
        len(tokens) == 4
        and tokens[0].type == 'ID' and tokens[0].value == 'grid'
        and tokens[1].type == 'ID' and tokens[1].value == 'random'
        and tokens[2].type == 'NUMBER'
        and tokens[3].type == 'NUMBER'
    ):
        return GridStmt(tokens[2].value, tokens[3].value, True)

    # entity lines: player/enemy/wall/goal
    if (
        len(tokens) >= 4
        and tokens[0].type == 'ID' and tokens[0].value in {'player', 'enemy', 'wall', 'goal'}
        and tokens[1].type == 'ID' and tokens[1].value == 'at'
        and tokens[2].type == 'NUMBER'
        and tokens[3].type == 'NUMBER'
    ):
        kind = tokens[0].value
        x = tokens[2].value
        y = tokens[3].value
        extra = None
        if len(tokens) == 6:
            if (
                tokens[4].type == 'ID' and tokens[4].value == 'moves'
                and tokens[5].type == 'ID'
            ):
                extra = {'moves': tokens[5].value}
            else:
                raise SyntaxError(f'Unrecognized line: {line}')
        elif len(tokens) != 4:
            raise SyntaxError(f'Unrecognized line: {line}')
        return EntityStmt(kind, x, y, extra)

    # score +/-N on EVENT
    if len(tokens) >= 4 and tokens[0].type == 'ID' and tokens[0].value == 'score':
        idx = 1
        sign = 1
        if tokens[idx].type in {'PLUS', 'MINUS'}:
            sign = -1 if tokens[idx].type == 'MINUS' else 1
            idx += 1

        if idx >= len(tokens) or tokens[idx].type != 'NUMBER':
            raise SyntaxError(f'Unrecognized line: {line}')
        amount = sign * tokens[idx].value
        idx += 1

        if idx >= len(tokens) or tokens[idx].type != 'ID' or tokens[idx].value != 'on':
            raise SyntaxError(f'Unrecognized line: {line}')
        idx += 1

        if idx >= len(tokens):
            raise SyntaxError(f'Unrecognized line: {line}')
        event = ' '.join(str(tok.value) for tok in tokens[idx:])
        return ScoreStmt(amount, event)

    # if A == B -> win|lose
    if (
        len(tokens) == 6
        and tokens[0].type == 'ID' and tokens[0].value == 'if'
        and tokens[1].type == 'ID'
        and tokens[2].type == 'EQ'
        and tokens[3].type == 'ID'
        and tokens[4].type == 'ARROW'
        and tokens[5].type == 'ID' and tokens[5].value in {'win', 'lose'}
    ):
        cond = RuleCond(tokens[1].value, '==', tokens[3].value)
        return RuleStmt(cond, tokens[5].value)

    raise SyntaxError(f'Unrecognized line: {line}')


def parse_lines(lines: List[str]) -> Program:
    prog = Program()
    i = 0
    while i < len(lines):
        raw = lines[i]
        if not raw.strip():
            i += 1
            continue
        parsed = parse_line(raw)
        if parsed == 'RULE_HEADER':
            # consume indented rule lines
            i += 1
            while i < len(lines) and (lines[i].startswith(' ') or lines[i].startswith('\t')):
                stmt = parse_line(lines[i])
                if stmt is not None:
                    prog.statements.append(stmt)
                i += 1
            continue
        if parsed is not None:
            prog.statements.append(parsed)
        i += 1
    return prog


def parse_text(text: str) -> Program:
    lines = text.splitlines()
    return parse_lines(lines)


def parse_file(path: str) -> Program:
    with open(path, 'r') as f:
        text = f.read()
    return parse_text(text)


def dump_ast(prog: Program):
    from pprint import pprint
    pprint(prog)


def generate_symbol_table(prog: Program):
    """Extract a list of symbols and their metadata from the AST."""
    symbols = []
    for stmt in prog.statements:
        if isinstance(stmt, GridStmt):
            symbols.append({"Symbol": "grid", "Type": "Config", "Value": f"{stmt.width}x{stmt.height}"})
        elif isinstance(stmt, EntityStmt):
            extra = f" (moves: {stmt.extra['moves']})" if stmt.extra and 'moves' in stmt.extra else ""
            symbols.append({"Symbol": stmt.kind, "Type": "Entity", "Value": f"at ({stmt.x}, {stmt.y}){extra}"})
        elif isinstance(stmt, ScoreStmt):
            symbols.append({"Symbol": "score", "Type": "Trigger", "Value": f"{stmt.amount:+d} on {stmt.event}"})
        elif isinstance(stmt, RuleStmt):
            symbols.append({"Symbol": "rule", "Type": "Condition", "Value": f"if {stmt.cond.left} {stmt.cond.op} {stmt.cond.right} -> {stmt.action}"})
    return symbols


def dump_symbol_table(prog: Program):
    """Print a formatted symbol table to stdout."""
    symbols = generate_symbol_table(prog)
    if not symbols:
        print("\n--- SYMBOL TABLE ---")
        print("Empty.")
        return

    headers = ["Symbol", "Type", "Value"]
    widths = {h: len(h) for h in headers}
    for row in symbols:
        for h in headers:
            widths[h] = max(widths[h], len(str(row[h])))

    print("\n--- SYMBOL TABLE ---")
    header_row = " | ".join(f"{h:<{widths[h]}}" for h in headers)
    print(header_row)
    print("-" * len(header_row))

    for row in symbols:
        print(" | ".join(f"{str(row[h]):<{widths[h]}}" for h in headers))
    print("--------------------\n")


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print('Usage: python -m gridlock.parser path/to/script')
        sys.exit(1)
    prog = parse_file(sys.argv[1])
    dump_ast(prog)
