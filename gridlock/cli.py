#!/usr/bin/env python3
"""CLI for Gridlock — loads, parses, and runs .grid scripts."""
import argparse
import sys
from . import __version__


def main():
    arg_parser = argparse.ArgumentParser(prog="gridlock", description="Gridlock DSL CLI")
    arg_parser.add_argument("script", nargs="?", help="Gridlock script file (.grid)")
    arg_parser.add_argument("--dump-tokens", action="store_true", help="Dump lexer tokens and exit")
    arg_parser.add_argument("--dump-ast",    action="store_true", help="Dump AST and exit")
    arg_parser.add_argument("--dump-symbols", action="store_true", help="Dump symbol table and exit")
    arg_parser.add_argument("--version",     action="store_true", help="Show version and exit")
    args = arg_parser.parse_args()

    if args.version:
        print(__version__)
        return

    if not args.script:
        arg_parser.print_help()
        sys.exit(1)

    # ── Dump tokens ──────────────────────────────────────────────────────────
    if args.dump_tokens:
        from .lexer import dump_tokens
        dump_tokens(args.script)
        return

    # ── Parse ────────────────────────────────────────────────────────────────
    from . import parser as _parser
    try:
        ast = _parser.parse_file(args.script)
    except SyntaxError as exc:
        print(f"[Parse Error] {exc}", file=sys.stderr)
        sys.exit(1)

    if args.dump_ast:
        _parser.dump_ast(ast)
        return

    if args.dump_symbols:
        _parser.dump_symbol_table(ast)
        return

    # ── Run game ─────────────────────────────────────────────────────────────
    _parser.dump_symbol_table(ast)
    input("Press Enter to start game...")

    from .engine import GameEngine
    engine = GameEngine()
    engine.load_program(ast)

    while True:
        engine.run()
        # After run() returns, ask if the user wants to restart
        answer = input("\nPlay again? [y/N]: ").strip().lower()
        if answer != "y":
            print("Thanks for playing Gridlock!! :D")
            break
        # Re-load a fresh state from the same file
        engine = GameEngine()
        ast = _parser.parse_file(args.script)
        engine.load_program(ast)


if __name__ == "__main__":
    main()
