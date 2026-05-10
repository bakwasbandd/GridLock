"""
tests/test_engine.py
--------------------
Unit tests for the Gridlock DSL — parser and GameEngine.
Run with:  python -m pytest tests/ -v
       or: python -m unittest discover -s tests -v
"""

import unittest
from unittest.mock import patch

from gridlock.parser import (
    parse_text,
    GridStmt,
    EntityStmt,
    ScoreStmt,
    RuleStmt,
)
from gridlock.engine import GameEngine


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _make_engine(script: str) -> GameEngine:
    """Parse *script* and return a loaded GameEngine."""
    prog = parse_text(script)
    engine = GameEngine()
    engine.load_program(prog)
    return engine


# ─────────────────────────────────────────────────────────────
# Parser Tests
# ─────────────────────────────────────────────────────────────

class TestParser(unittest.TestCase):

    def test_grid_statement(self):
        prog = parse_text("grid 10 8")
        self.assertEqual(len(prog.statements), 1)
        stmt = prog.statements[0]
        self.assertIsInstance(stmt, GridStmt)
        self.assertEqual(stmt.width, 10)
        self.assertEqual(stmt.height, 8)

    def test_random_grid_statement(self):
        prog = parse_text("grid random 10 8")
        stmt = prog.statements[0]
        self.assertIsInstance(stmt, GridStmt)
        self.assertTrue(stmt.randomized)
        self.assertEqual(stmt.width, 10)
        self.assertEqual(stmt.height, 8)

    def test_player_statement(self):
        prog = parse_text("grid 5 5\nplayer at 1 2")
        stmts = {type(s).__name__: s for s in prog.statements}
        self.assertIn("EntityStmt", stmts)
        p = stmts["EntityStmt"]
        self.assertEqual(p.kind, "player")
        self.assertEqual(p.x, 1)
        self.assertEqual(p.y, 2)

    def test_enemy_with_moves(self):
        prog = parse_text("grid 5 5\nenemy at 3 3 moves random")
        entity = next(s for s in prog.statements if isinstance(s, EntityStmt))
        self.assertEqual(entity.kind, "enemy")
        self.assertEqual(entity.extra, {"moves": "random"})

    def test_wall_statement(self):
        prog = parse_text("grid 5 5\nwall at 2 2")
        entity = next(s for s in prog.statements if isinstance(s, EntityStmt))
        self.assertEqual(entity.kind, "wall")

    def test_goal_statement(self):
        prog = parse_text("grid 5 5\ngoal at 4 4")
        entity = next(s for s in prog.statements if isinstance(s, EntityStmt))
        self.assertEqual(entity.kind, "goal")

    def test_score_positive(self):
        prog = parse_text("score +10 on reach goal")
        stmt = next(s for s in prog.statements if isinstance(s, ScoreStmt))
        self.assertEqual(stmt.amount, 10)
        self.assertEqual(stmt.event, "reach goal")

    def test_score_negative(self):
        prog = parse_text("score -5 on hit enemy")
        stmt = next(s for s in prog.statements if isinstance(s, ScoreStmt))
        self.assertEqual(stmt.amount, -5)
        self.assertEqual(stmt.event, "hit enemy")

    def test_rule_win(self):
        prog = parse_text("rule:\n  if player == goal -> win")
        stmt = next(s for s in prog.statements if isinstance(s, RuleStmt))
        self.assertEqual(stmt.cond.left, "player")
        self.assertEqual(stmt.cond.right, "goal")
        self.assertEqual(stmt.action, "win")

    def test_rule_lose(self):
        prog = parse_text("rule:\n  if player == enemy -> lose")
        stmt = next(s for s in prog.statements if isinstance(s, RuleStmt))
        self.assertEqual(stmt.action, "lose")

    def test_blank_and_comment_lines_ignored(self):
        prog = parse_text("grid 5 5\n\n# this is a comment\nplayer at 0 0")
        # Should only have GridStmt + EntityStmt, no None
        self.assertEqual(len(prog.statements), 2)

    def test_syntax_error_on_unknown_line(self):
        with self.assertRaises(SyntaxError):
            parse_text("this is not valid")

    def test_full_script_parses(self):
        script = (
            "grid 10 10\n"
            "player at 0 0\n"
            "enemy at 5 5 moves random\n"
            "wall at 3 3\n"
            "wall at 3 4\n"
            "goal at 9 9\n"
            "score +10 on reach goal\n"
            "score -5 on hit enemy\n"
            "rule:\n"
            "  if player == enemy -> lose\n"
            "  if player == goal -> win\n"
        )
        prog = parse_text(script)
        kinds = [type(s).__name__ for s in prog.statements]
        self.assertIn("GridStmt", kinds)
        self.assertIn("EntityStmt", kinds)
        self.assertIn("ScoreStmt", kinds)
        self.assertIn("RuleStmt", kinds)


# ─────────────────────────────────────────────────────────────
# Engine — Load
# ─────────────────────────────────────────────────────────────

class TestEngineLoad(unittest.TestCase):

    def test_grid_dimensions_loaded(self):
        engine = _make_engine("grid 7 5")
        self.assertEqual(engine.width, 7)
        self.assertEqual(engine.height, 5)

    def test_entities_loaded(self):
        engine = _make_engine("grid 5 5\nplayer at 0 0\nenemy at 4 4 moves random\nwall at 2 2\ngoal at 4 0")
        kinds = {e.kind for e in engine.entities}
        self.assertIn("player", kinds)
        self.assertIn("enemy", kinds)
        self.assertIn("wall", kinds)
        self.assertIn("goal", kinds)

    def test_initial_score_zero(self):
        engine = _make_engine("grid 5 5\nplayer at 0 0")
        self.assertEqual(engine.score, 0)

    def test_initial_status_running(self):
        engine = _make_engine("grid 5 5\nplayer at 0 0")
        self.assertEqual(engine.status, "running")

    def test_random_grid_mode_generates_bounds_and_places_entities(self):
        import random
        from collections import deque

        random.seed(7)
        engine = _make_engine(
            "grid random 10 10\n"
            "player at 0 0\n"
            "enemy at 5 5 moves random\n"
            "goal at 9 9\n"
        )

        self.assertGreaterEqual(engine.width, 6)
        self.assertLessEqual(engine.width, 10)
        self.assertGreaterEqual(engine.height, 6)
        self.assertLessEqual(engine.height, 10)

        for entity in engine.entities:
            self.assertGreaterEqual(entity.x, 0)
            self.assertGreaterEqual(entity.y, 0)
            self.assertLess(entity.x, engine.width)
            self.assertLess(entity.y, engine.height)

        player = engine._get_entity("player")
        enemy = engine._get_entity("enemy")
        goal = engine._get_entity("goal")

        self.assertGreaterEqual(abs(player.x - enemy.x) + abs(player.y - enemy.y), 3)
        self.assertGreaterEqual(abs(player.x - goal.x) + abs(player.y - goal.y), 3)

        walls = {(entity.x, entity.y) for entity in engine.entities if entity.kind == "wall"}
        start = (player.x, player.y)
        target = (goal.x, goal.y)
        queue = deque([start])
        seen = {start}

        while queue:
            x, y = queue.popleft()
            if (x, y) == target:
                break
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if not (0 <= nx < engine.width and 0 <= ny < engine.height):
                    continue
                if (nx, ny) in walls or (nx, ny) in seen:
                    continue
                seen.add((nx, ny))
                queue.append((nx, ny))

        self.assertIn(target, seen)


# ─────────────────────────────────────────────────────────────
# Engine — Movement & Boundaries
# ─────────────────────────────────────────────────────────────

class TestPlayerMovement(unittest.TestCase):

    def _player(self, engine: GameEngine):
        return engine._get_entity("player")

    def test_move_right(self):
        engine = _make_engine("grid 5 5\nplayer at 0 0")
        engine.move_player("d")
        self.assertEqual(self._player(engine).x, 1)
        self.assertEqual(self._player(engine).y, 0)

    def test_move_down(self):
        engine = _make_engine("grid 5 5\nplayer at 0 0")
        engine.move_player("s")
        self.assertEqual(self._player(engine).y, 1)

    def test_move_left(self):
        engine = _make_engine("grid 5 5\nplayer at 2 2")
        engine.move_player("a")
        self.assertEqual(self._player(engine).x, 1)

    def test_move_up(self):
        engine = _make_engine("grid 5 5\nplayer at 2 2")
        engine.move_player("w")
        self.assertEqual(self._player(engine).y, 1)

    def test_boundary_left_edge(self):
        """Player at x=0 cannot move further left."""
        engine = _make_engine("grid 5 5\nplayer at 0 2")
        engine.move_player("a")
        self.assertEqual(self._player(engine).x, 0)

    def test_boundary_right_edge(self):
        """Player at x=width-1 cannot move further right."""
        engine = _make_engine("grid 5 5\nplayer at 4 2")
        engine.move_player("d")
        self.assertEqual(self._player(engine).x, 4)

    def test_boundary_top_edge(self):
        engine = _make_engine("grid 5 5\nplayer at 2 0")
        engine.move_player("w")
        self.assertEqual(self._player(engine).y, 0)

    def test_boundary_bottom_edge(self):
        engine = _make_engine("grid 5 5\nplayer at 2 4")
        engine.move_player("s")
        self.assertEqual(self._player(engine).y, 4)

    def test_unknown_direction_ignored(self):
        engine = _make_engine("grid 5 5\nplayer at 2 2")
        engine.move_player("x")   # invalid key
        self.assertEqual(self._player(engine).x, 2)
        self.assertEqual(self._player(engine).y, 2)


# ─────────────────────────────────────────────────────────────
# Engine — Wall Collision
# ─────────────────────────────────────────────────────────────

class TestWallCollision(unittest.TestCase):

    def _player(self, engine: GameEngine):
        return engine._get_entity("player")

    def test_wall_blocks_right(self):
        """Wall directly to the right should block the player."""
        engine = _make_engine("grid 5 5\nplayer at 1 1\nwall at 2 1")
        engine.move_player("d")
        self.assertEqual(self._player(engine).x, 1)   # stayed put

    def test_wall_blocks_down(self):
        engine = _make_engine("grid 5 5\nplayer at 1 1\nwall at 1 2")
        engine.move_player("s")
        self.assertEqual(self._player(engine).y, 1)

    def test_wall_blocks_left(self):
        engine = _make_engine("grid 5 5\nplayer at 2 2\nwall at 1 2")
        engine.move_player("a")
        self.assertEqual(self._player(engine).x, 2)

    def test_wall_blocks_up(self):
        engine = _make_engine("grid 5 5\nplayer at 2 2\nwall at 2 1")
        engine.move_player("w")
        self.assertEqual(self._player(engine).y, 2)

    def test_non_adjacent_wall_does_not_block(self):
        """A wall two cells away should not block movement."""
        engine = _make_engine("grid 5 5\nplayer at 1 1\nwall at 3 1")
        engine.move_player("d")
        self.assertEqual(self._player(engine).x, 2)   # moved normally


# ─────────────────────────────────────────────────────────────
# Engine — Rule Evaluation (Win / Lose)
# ─────────────────────────────────────────────────────────────

class TestRuleEvaluation(unittest.TestCase):

    def _engine_with_rules(self):
        """5x5 grid: player at (0,0), enemy at (4,0), goal at (4,4)."""
        script = (
            "grid 5 5\n"
            "player at 0 0\n"
            "enemy at 4 0 moves random\n"
            "goal at 4 4\n"
            "score +10 on reach goal\n"
            "score -5 on hit enemy\n"
            "rule:\n"
            "  if player == enemy -> lose\n"
            "  if player == goal -> win\n"
        )
        engine = _make_engine(script)
        # Pin the enemy so it doesn't move randomly during tests
        enemy = engine._get_entity("enemy")
        enemy.moves = None
        return engine

    def test_player_reaches_goal_wins(self):
        """Walk player to goal cell → evaluate_rules → win."""
        engine = self._engine_with_rules()
        player = engine._get_entity("player")
        goal   = engine._get_entity("goal")
        # Teleport player directly onto the goal (bypassing move, like end-of-step)
        player.x, player.y = goal.x, goal.y
        engine.evaluate_rules()
        self.assertEqual(engine.status, "win")

    def test_player_hits_enemy_loses(self):
        """Move player onto enemy cell → evaluate_rules → lose."""
        engine = self._engine_with_rules()
        player = engine._get_entity("player")
        enemy  = engine._get_entity("enemy")
        # Teleport player onto the enemy
        player.x, player.y = enemy.x, enemy.y
        engine.evaluate_rules()
        self.assertEqual(engine.status, "lose")

    def test_no_collision_status_running(self):
        engine = self._engine_with_rules()
        engine.evaluate_rules()
        self.assertEqual(engine.status, "running")

    def test_step_after_game_over_ignored(self):
        """Once status != 'running', step() should do nothing."""
        engine = self._engine_with_rules()
        player = engine._get_entity("player")
        goal   = engine._get_entity("goal")
        player.x, player.y = goal.x, goal.y
        engine.evaluate_rules()          # sets status = 'win'
        self.assertEqual(engine.status, "win")
        old_x, old_y = player.x, player.y
        engine.step("a")                 # must be ignored
        self.assertEqual(player.x, old_x)
        self.assertEqual(player.y, old_y)


class TestEnemyChasing(unittest.TestCase):

    def test_enemy_chase_mode_moves_towards_player(self):
        engine = _make_engine("grid 5 5\nplayer at 0 0\nenemy at 4 0 moves chase")
        enemy = engine._get_entity("enemy")

        engine._move_enemies()

        self.assertEqual(enemy.x, 3)
        self.assertEqual(enemy.y, 0)

    def test_enemy_random_mode_uses_random_direction(self):
        engine = _make_engine("grid 5 5\nplayer at 0 0\nenemy at 4 0 moves random")
        enemy = engine._get_entity("enemy")

        # Force random movement to go down; chase would have gone left.
        with patch("gridlock.engine.random.choice", return_value=(0, 1)):
            engine._move_enemies()

        self.assertEqual(enemy.x, 4)
        self.assertEqual(enemy.y, 1)


# ─────────────────────────────────────────────────────────────
# Engine — Scoring
# ─────────────────────────────────────────────────────────────

class TestScoring(unittest.TestCase):

    def test_score_increases_on_win(self):
        script = (
            "grid 5 5\n"
            "player at 0 0\n"
            "goal at 4 4\n"
            "score +10 on reach goal\n"
            "rule:\n"
            "  if player == goal -> win\n"
        )
        engine = _make_engine(script)
        # Move player onto the goal manually to simulate reaching it
        player = engine._get_entity("player")
        goal   = engine._get_entity("goal")
        player.x, player.y = goal.x, goal.y
        engine.evaluate_rules()
        self.assertEqual(engine.score, 10)

    def test_score_decreases_on_lose(self):
        script = (
            "grid 5 5\n"
            "player at 0 0\n"
            "enemy at 4 4 moves random\n"
            "score -5 on hit enemy\n"
            "rule:\n"
            "  if player == enemy -> lose\n"
        )
        engine = _make_engine(script)
        player = engine._get_entity("player")
        enemy  = engine._get_entity("enemy")
        player.x, player.y = enemy.x, enemy.y
        engine.evaluate_rules()
        self.assertEqual(engine.score, -5)

    def test_score_unchanged_when_no_event(self):
        script = (
            "grid 5 5\n"
            "player at 0 0\n"
            "goal at 4 4\n"
            "score +10 on reach goal\n"
            "rule:\n"
            "  if player == goal -> win\n"
        )
        engine = _make_engine(script)
        engine.evaluate_rules()
        self.assertEqual(engine.score, 0)


# ─────────────────────────────────────────────────────────────
# Engine — Rendering (smoke test)
# ─────────────────────────────────────────────────────────────

class TestRenderer(unittest.TestCase):

    def test_render_returns_string(self):
        engine = _make_engine("grid 5 5\nplayer at 0 0\ngoal at 4 4")
        output = engine.render()
        self.assertIsInstance(output, str)

    def test_render_contains_player_symbol(self):
        engine = _make_engine("grid 5 5\nplayer at 0 0")
        self.assertIn("P", engine.render())

    def test_render_contains_score(self):
        engine = _make_engine("grid 5 5\nplayer at 0 0")
        self.assertIn("Score:", engine.render())

    def test_render_grid_dimensions(self):
        """Rendered grid should have height+2 border lines."""
        engine = _make_engine("grid 4 3\nplayer at 0 0")
        lines = [l for l in engine.render().splitlines() if "│" in l or "┌" in l or "└" in l]
        # 3 rows + top border + bottom border = 5 lines with box chars
        self.assertEqual(len(lines), 5)


if __name__ == "__main__":
    unittest.main()
