# Gridlock DSL — Grammar (informal)

This document describes a simple, line-based grammar for the Gridlock DSL used
by the project. The implementation will use a small tokenizer + recursive-descent
parser.

Top-level program:

program  := statement*

Statements (one per line, order independent except for `rule` blocks):

- grid W H                ; define grid width and height (numbers)
- grid random MAXW MAXH   ; procedurally generate a random grid up to the given bounds
- player at X Y           ; place player
- enemy at X Y moves PATTERN
- wall at X Y             ; place wall
- goal at X Y             ; place goal
- score +/-N on EVENT     ; scoring rules (EVENT: reach goal, hit enemy)
- rule:                   ; followed by indented rule lines
    if cond -> action

Where `cond` examples:
- player == enemy
- player == goal

Actions: `win`, `lose` (can extend later).

Tokens
- Keywords: `grid`, `player`, `enemy`, `wall`, `goal`, `score`, `rule`, `if`, `moves`, `at`, `on`
- Operators/symbols: `->`, `==`, `:`, `+`, `-`
- NUMBER: integer literals
- ID: identifiers like `random`, `patrol`

Notes and simplicity decisions:
- The language is line-oriented; block following `rule:` is determined by
  indentation (leading spaces) or any lines until the next top-level statement.
- Overlapping entities are auto-resolved by moving the later entity to the next
  free cell (engine policy).
- Enemy movement patterns are ignored by the engine; enemies always chase the player,
  with a random fallback if blocked.
- When using `grid random ...`, the engine generates the actual dimensions,
  places entities randomly within the grid, and keeps at least one open path
  between the player and the goal.

Example
```
grid 10 10
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
