# Gridlock

Gridlock is a small Python interpreter for a line-based game DSL. A `.grid`
file describes a grid, places entities such as the player, enemies, walls, and
the goal, then runs the result as an interactive terminal game.

## Project Layout

```text
gridlock/
  cli.py        Command-line interface
  __main__.py   Enables `python -m gridlock`
  lexer.py      Tokenizer for `.grid` scripts
  parser.py     Parser and AST helpers
  engine.py     Interactive game runtime

examples/
  sample.grid   Example Gridlock script

tests/
  test_engine.py
```

## Requirements

- Python 3.10 or newer
- Dependencies from `requirements.txt`

Install dependencies from the repository root:

```powershell
pip install -r requirements.txt
```

## Run the Example

From the repository root:

```powershell
python -m gridlock examples/sample.grid
```

On Windows, this also works:

```powershell
python -m gridlock examples\sample.grid
```

The program prints the parsed symbol table first. Press Enter to start the game,
then follow the terminal prompts to move the player around the grid.

## CLI Commands

Show the installed Gridlock version:

```powershell
python -m gridlock --version
```

Dump lexer tokens without running the game:

```powershell
python -m gridlock examples/sample.grid --dump-tokens
```

Dump the parsed AST:

```powershell
python -m gridlock examples/sample.grid --dump-ast
```

Dump the symbol table:

```powershell
python -m gridlock examples/sample.grid --dump-symbols
```

## Gridlock Script Example

```grid
grid random 10 10

player at 0 0

enemy at 5 5 moves random

wall at 3 3
wall at 3 4

goal at 9 9

score +10 on reach goal
score -5 on hit enemy

rule:
  if player == enemy -> lose
  if player == goal -> win
```

## Language Basics

Gridlock scripts are line-oriented. Common statements include:

```grid
grid 10 10
grid random 10 10
player at 0 0
enemy at 5 5 moves random
wall at 3 3
goal at 9 9
score +10 on reach goal
score -5 on hit enemy
rule:
  if player == enemy -> lose
  if player == goal -> win
```

See `grammar.md` for a more complete informal grammar.

## Run Tests

Using `unittest`:

```powershell
python -m unittest discover -s tests -v
```

If `pytest` is installed, you can also run:

```powershell
python -m pytest tests/ -v
```
