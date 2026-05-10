import re
from dataclasses import dataclass
from typing import Iterator, List

TOKEN_SPEC = [
    ('ARROW', r'->'),
    ('EQ', r'=='),
    ('NUMBER', r'\d+'),
    ('PLUS', r'\+'),
    ('MINUS', r'-'),
    ('COLON', r':'),
    ('ID', r'[A-Za-z_][A-Za-z0-9_]*'),
    ('NEWLINE', r'\n'),
    ('SKIP', r'[ \t]+'),
    ('MISMATCH', r'.'),
]

master_pat = re.compile('|'.join(f"(?P<{name}>{pattern})" for name, pattern in TOKEN_SPEC))

@dataclass
class Token:
    type: str
    value: str
    line: int
    column: int

    def __repr__(self):
        return f"Token({self.type!r}, {self.value!r}, line={self.line}, col={self.column})"

def tokenize(text: str) -> Iterator[Token]:
    line_num = 1
    line_start = 0
    for mo in master_pat.finditer(text):
        kind = mo.lastgroup
        value = mo.group()
        column = mo.start() - line_start + 1
        if kind == 'NUMBER':
            yield Token('NUMBER', int(value), line_num, column)
        elif kind == 'ID':
            yield Token('ID', value, line_num, column)
        elif kind == 'NEWLINE':
            line_num += 1
            line_start = mo.end()
            yield Token('NEWLINE', '\n', line_num-1, column)
        elif kind == 'SKIP':
            continue
        elif kind == 'MISMATCH':
            raise SyntaxError(f'Unexpected character {value!r} at line {line_num} col {column}')
        else:
            yield Token(kind, value, line_num, column)

def dump_tokens(path: str):
    with open(path, 'r') as f:
        text = f.read()
    for tok in tokenize(text):
        print(tok)

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print('Usage: python -m gridlock.lexer path/to/script')
        sys.exit(1)
    dump_tokens(sys.argv[1])
