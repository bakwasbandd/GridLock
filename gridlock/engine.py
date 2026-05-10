"""
gridlock/engine.py
------------------
Execution engine for the Gridlock DSL.
Loads a parsed AST and runs the game as an interactive terminal session.
"""

import os
import random
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .parser import (
    EntityStmt,
    GridStmt,
    Program,
    RuleStmt,
    ScoreStmt,
)

# ─────────────────────────────────────────────
# Direction helpers
# ─────────────────────────────────────────────

DIRECTIONS: Dict[str, Tuple[int, int]] = {
    "w": (0, -1),   # up
    "a": (-1, 0),   # left
    "s": (0, 1),    # down
    "d": (1, 0),    # right
}

# ─────────────────────────────────────────────
# Entity data class (used at runtime)
# ─────────────────────────────────────────────

@dataclass
class Entity:
    kind: str          # 'player', 'enemy', 'wall', 'goal'
    x: int
    y: int
    moves: Optional[str] = None   # movement pattern ('random' or None)


# ─────────────────────────────────────────────
# Game Engine
# ─────────────────────────────────────────────

class GameEngine:
    """Interprets and executes a Gridlock program."""

    def __init__(self) -> None:
        self.width: int = 0
        self.height: int = 0
        self.entities: List[Entity] = []
        self.score: int = 0
        self.score_rules: List[ScoreStmt] = []
        self.rules: List[RuleStmt] = []
        self.status: str = "running"   # 'running' | 'win' | 'lose'
        self.message: str = ""

    # ── Loader ──────────────────────────────

    def load_program(self, prog: Program) -> None:
        """Populate engine state from a parsed AST."""
        self.entities.clear()
        self.score_rules.clear()
        self.rules.clear()
        self.score = 0
        self.status = "running"
        self.message = ""
        self.width = 0
        self.height = 0

        occupied: set = set()
        random_grid = False
        anchor_positions: List[Tuple[int, int]] = []
        player_position: Optional[Tuple[int, int]] = None
        goal_position: Optional[Tuple[int, int]] = None

        for stmt in prog.statements:
            if isinstance(stmt, GridStmt):
                random_grid = stmt.randomized
                if stmt.randomized:
                    self.width = random.randint(min(6, stmt.width), stmt.width)
                    self.height = random.randint(min(6, stmt.height), stmt.height)
                else:
                    self.width = stmt.width
                    self.height = stmt.height

            elif isinstance(stmt, EntityStmt):
                if random_grid:
                    if stmt.kind == "player" and player_position is None:
                        x, y = self._smart_random_position(stmt.kind, occupied, anchor_positions)
                        player_position = (x, y)
                    elif stmt.kind == "goal" and goal_position is None:
                        x, y = self._smart_random_position(stmt.kind, occupied, anchor_positions)
                        goal_position = (x, y)
                    elif stmt.kind == "wall" and player_position and goal_position:
                        x, y = self._smart_random_wall_position(
                            occupied,
                            anchor_positions,
                            player_position,
                            goal_position,
                        )
                    else:
                        x, y = self._smart_random_position(stmt.kind, occupied, anchor_positions)
                else:
                    x, y = self._resolve_position(stmt.x, stmt.y, occupied)
                moves = stmt.extra.get("moves") if stmt.extra else None
                ent = Entity(stmt.kind, x, y, moves)
                self.entities.append(ent)
                occupied.add((x, y))
                if stmt.kind in {"player", "enemy", "goal"}:
                    anchor_positions.append((x, y))

            elif isinstance(stmt, ScoreStmt):
                self.score_rules.append(stmt)

            elif isinstance(stmt, RuleStmt):
                self.rules.append(stmt)

    def _resolve_position(self, x: int, y: int, occupied: set) -> Tuple[int, int]:
        """If a cell is taken, find the next free cell."""
        if (x, y) not in occupied:
            return x, y
        # Scan row-by-row until a free cell is found
        for cy in range(self.height):
            for cx in range(self.width):
                if (cx, cy) not in occupied:
                    return cx, cy
        raise RuntimeError("Grid is completely full — cannot place entity.")

    def _random_free_position(self, occupied: set) -> Tuple[int, int]:
        """Pick a random unoccupied cell inside the current grid."""
        candidates = [
            (x, y)
            for y in range(self.height)
            for x in range(self.width)
            if (x, y) not in occupied
        ]
        if not candidates:
            raise RuntimeError("Grid is completely full — cannot place entity.")
        return random.choice(candidates)

    def _smart_random_position(
        self,
        kind: str,
        occupied: set,
        anchors: List[Tuple[int, int]],
    ) -> Tuple[int, int]:
        """Prefer positions that keep the opening state spread out."""
        candidates = [
            (x, y)
            for y in range(self.height)
            for x in range(self.width)
            if (x, y) not in occupied
        ]
        if not candidates:
            raise RuntimeError("Grid is completely full — cannot place entity.")

        if not anchors:
            return random.choice(candidates)

        # Prefer cells that are at least a little separated from existing anchors.
        min_distance = 3 if kind in {"player", "enemy", "goal"} else 1
        far_enough = [
            (x, y)
            for x, y in candidates
            if all(abs(x - ax) + abs(y - ay) >= min_distance for ax, ay in anchors)
        ]
        if far_enough:
            return random.choice(far_enough)

        # If the grid is small or crowded, fall back to the best available cell.
        best_score = max(
            min(abs(x - ax) + abs(y - ay) for ax, ay in anchors)
            for x, y in candidates
        )
        best_candidates = [
            (x, y)
            for x, y in candidates
            if min(abs(x - ax) + abs(y - ay) for ax, ay in anchors) == best_score
        ]
        return random.choice(best_candidates)

    def _smart_random_wall_position(
        self,
        occupied: set,
        anchors: List[Tuple[int, int]],
        player_position: Tuple[int, int],
        goal_position: Tuple[int, int],
    ) -> Tuple[int, int]:
        """Place walls away from a guaranteed corridor between player and goal."""
        protected = set(self._corridor_cells(player_position, goal_position))
        candidates = [
            (x, y)
            for y in range(self.height)
            for x in range(self.width)
            if (x, y) not in occupied and (x, y) not in protected
        ]
        if not candidates:
            return self._smart_random_position("wall", occupied, anchors)

        # Prefer cells away from both anchors to keep the corridor open and
        # avoid spawning walls right next to the player or goal.
        best_score = max(
            min(abs(x - ax) + abs(y - ay) for ax, ay in anchors)
            for x, y in candidates
        )
        best_candidates = [
            (x, y)
            for x, y in candidates
            if min(abs(x - ax) + abs(y - ay) for ax, ay in anchors) == best_score
        ]
        return random.choice(best_candidates)

    def _corridor_cells(
        self,
        start: Tuple[int, int],
        end: Tuple[int, int],
    ) -> List[Tuple[int, int]]:
        """Build a simple L-shaped corridor from start to end."""
        cells = [start]
        x, y = start
        target_x, target_y = end

        step_x = 1 if target_x > x else -1
        while x != target_x:
            x += step_x
            cells.append((x, y))

        step_y = 1 if target_y > y else -1
        while y != target_y:
            y += step_y
            cells.append((x, y))

        return cells

    # ── Lookups ─────────────────────────────

    def _get_entity(self, kind: str) -> Optional[Entity]:
        for e in self.entities:
            if e.kind == kind:
                return e
        return None

    def _walls(self) -> List[Entity]:
        return [e for e in self.entities if e.kind == "wall"]

    def _enemies(self) -> List[Entity]:
        return [e for e in self.entities if e.kind == "enemy"]

    # ── Movement ────────────────────────────

    def _clamp(self, val: int, lo: int, hi: int) -> int:
        return max(lo, min(hi, val))

    def _is_wall(self, x: int, y: int) -> bool:
        return any(w.x == x and w.y == y for w in self._walls())

    def _try_move(self, entity: Entity, dx: int, dy: int) -> bool:
        """Attempt to move *entity* by (dx, dy). Returns True if moved."""
        nx = self._clamp(entity.x + dx, 0, self.width - 1)
        ny = self._clamp(entity.y + dy, 0, self.height - 1)
        if self._is_wall(nx, ny):
            return False
        entity.x = nx
        entity.y = ny
        return True

    def move_player(self, direction: str) -> None:
        """Move the player in the given direction key (w/a/s/d)."""
        if self.status != "running":
            return
        delta = DIRECTIONS.get(direction.lower())
        if delta is None:
            return
        player = self._get_entity("player")
        if player:
            self._try_move(player, *delta)

    def _move_enemies(self) -> None:
        """Advance every enemy according to its movement pattern."""
        for enemy in self._enemies():
            movement_mode = (enemy.moves or "chase").lower()

            if movement_mode == "random":
                dx_r, dy_r = random.choice(list(DIRECTIONS.values()))
                self._try_move(enemy, dx_r, dy_r)
                continue

            player = self._get_entity("player")
            if not player:
                continue

            dx = player.x - enemy.x
            dy = player.y - enemy.y
            sx = 0 if dx == 0 else (1 if dx > 0 else -1)
            sy = 0 if dy == 0 else (1 if dy > 0 else -1)

            # Prioritise the larger axis to make movement feel deliberate.
            moved = False
            if abs(dx) >= abs(dy):
                if sx != 0:
                    moved = self._try_move(enemy, sx, 0)
                if not moved and sy != 0:
                    moved = self._try_move(enemy, 0, sy)
            else:
                if sy != 0:
                    moved = self._try_move(enemy, 0, sy)
                if not moved and sx != 0:
                    moved = self._try_move(enemy, sx, 0)

            # If both direct approaches are blocked, try a random step.
            if not moved:
                dx_r, dy_r = random.choice(list(DIRECTIONS.values()))
                self._try_move(enemy, dx_r, dy_r)

    # ── Rule & Score Evaluation ──────────────

    def _entity_at(self, x: int, y: int) -> Optional[Entity]:
        """Return the first non-wall entity at (x, y), or None."""
        for e in self.entities:
            if e.kind != "wall" and e.x == x and e.y == y:
                return e
        return None

    def _apply_scoring(self, event: str) -> None:
        for sr in self.score_rules:
            if sr.event == event:
                self.score += sr.amount

    def evaluate_rules(self) -> None:
        """Check all rules and update game status."""
        player = self._get_entity("player")
        if player is None:
            return

        for rule in self.rules:
            left = rule.cond.left    # e.g. 'player'
            right = rule.cond.right  # e.g. 'enemy' | 'goal'
            action = rule.action     # 'win' | 'lose'

            if left != "player":
                continue

            other = self._get_entity(right)
            if other and player.x == other.x and player.y == other.y:
                # Trigger matching score event
                event_map = {
                    "enemy": "hit enemy",
                    "goal": "reach goal",
                }
                event = event_map.get(right)
                if event:
                    self._apply_scoring(event)

                self.status = action
                self.message = (
                    "🎉 You reached the goal — YOU WIN!" if action == "win"
                    else "💀 You were caught by an enemy — YOU LOSE!"
                )
                return

    # ── One game step ────────────────────────

    def step(self, player_direction: str) -> None:
        """Execute one full turn: move player → move enemies → evaluate."""
        if self.status != "running":
            return
        self.move_player(player_direction)
        self._move_enemies()
        self.evaluate_rules()

    # ── ASCII Renderer ───────────────────────

    SYMBOLS = {
        "player": "P",
        "enemy":  "E",
        "goal":   "G",
        "wall":   "#",
    }
    # Colour codes (ANSI)
    COLOURS = {
        "player": "\033[92m",   # bright green
        "enemy":  "\033[91m",   # bright red
        "goal":   "\033[93m",   # bright yellow
        "wall":   "\033[90m",   # dark grey
    }
    RESET = "\033[0m"

    def render(self) -> str:
        """Return a full ASCII rendering of the grid as a string."""
        # Build a cell lookup for fast rendering
        cell: Dict[Tuple[int, int], Entity] = {}
        # Place in reverse so player is drawn on top
        for e in reversed(self.entities):
            cell[(e.x, e.y)] = e

        lines: List[str] = []

        # Top border
        lines.append("┌" + "──" * self.width + "┐")

        for row in range(self.height):
            row_chars = ["│"]
            for col in range(self.width):
                ent = cell.get((col, row))
                if ent:
                    sym = self.SYMBOLS.get(ent.kind, "?")
                    col_code = self.COLOURS.get(ent.kind, "")
                    row_chars.append(f"{col_code}{sym}{self.RESET} ")
                else:
                    row_chars.append(". ")
            row_chars.append("│")
            lines.append("".join(row_chars))

        # Bottom border
        lines.append("└" + "──" * self.width + "┘")

        # HUD
        status_str = {
            "running": "\033[94mRunning\033[0m",
            "win":     "\033[92mWIN\033[0m",
            "lose":    "\033[91mLOSE\033[0m",
        }.get(self.status, self.status)

        lines.append(f"  Score: {self.score}   Status: {status_str}")
        if self.message:
            lines.append(f"  {self.message}")
        lines.append("  Controls: W=up  A=left  S=down  D=right  Q=quit")

        return "\n".join(lines)

    # ── Interactive Game Loop ─────────────────

    def run(self) -> None:
        """Start the interactive terminal game loop."""
        self._clear_screen()
        print(self.render())

        while True:
            key = self._get_key()
            if key is None:
                continue
            if key == "q":
                print("\nExiting game. Goodbye!")
                break

            if self.status != "running":
                print("\nGame over. Press Q to quit or R to restart.")
                if key == "r":
                    # Caller must reload; we just break so cli can restart.
                    break
                continue

            self.step(key)
            self._clear_screen()
            print(self.render())

            if self.status != "running":
                # One final frame already printed; wait for Q/R
                continue

    @staticmethod
    def _clear_screen() -> None:
        os.system("cls" if os.name == "nt" else "clear")

    @staticmethod
    def _get_key() -> Optional[str]:
        """Read a single character from stdin without pressing Enter."""
        try:
            if os.name == "nt":           # Windows
                import msvcrt
                ch = msvcrt.getwch()
                return ch.lower()
            else:                          # Unix/Mac
                import tty, termios
                fd = sys.stdin.fileno()
                old_settings = termios.tcgetattr(fd)
                try:
                    tty.setraw(fd)
                    ch = sys.stdin.read(1)
                finally:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                return ch.lower()
        except Exception:
            return None
