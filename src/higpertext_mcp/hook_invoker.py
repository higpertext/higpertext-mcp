"""Stable DB-backed entry point, with explicit native transport selection."""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import io
import json
import sys

from higpertext_mcp import hook_protocol, hook_runner


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("hook_id")
    parser.add_argument("--assistant", choices=tuple(hook_protocol.EVENTS))
    parser.add_argument("--event")
    args = parser.parse_args()
    if bool(args.assistant) != bool(args.event):
        parser.error("--assistant and --event must be supplied together")
    if args.assistant and args.event not in hook_protocol.EVENTS[args.assistant]:
        parser.error("event unsupported by selected assistant")
    try:
        # Legacy wiring remains compatible. New wiring explicitly identifies its protocol.
        if not args.assistant:
            path = asyncio.run(hook_runner.resolve_hook_script(args.hook_id))
            sys.exit(hook_runner.run_hook(path))
        payload = hook_protocol.normalize(args.assistant, args.event, json.load(sys.stdin))
        path = asyncio.run(hook_runner.resolve_hook_script(args.hook_id))
        captured = io.StringIO()
        original_stdin = sys.stdin
        try:
            sys.stdin = io.StringIO(json.dumps(payload))
            with contextlib.redirect_stdout(captured):
                try:
                    code = hook_runner.run_hook(path)
                except SystemExit as exc:
                    code = exc.code
        finally:
            sys.stdin = original_stdin
        if code not in (None, 0):
            raise RuntimeError(f"hook process exited with status {code}")
        output = json.loads(captured.getvalue())
        # Existing DB hook decorators report exceptions as an error plus continue.
        if output.get("error"):
            raise RuntimeError("hook reported an evaluation error")
        print(json.dumps(hook_protocol.encode(args.assistant, args.event, output)))
    except Exception as exc:
        print(f"higpertext hook failed: {type(exc).__name__}", file=sys.stderr)
        if args.assistant:
            if args.event == "PreToolUse":
                denied = {"hookSpecificOutput": {"permissionDecision": "deny", "permissionDecisionReason": "higpertext could not evaluate the configured hook"}}
                print(json.dumps(hook_protocol.encode(args.assistant, args.event, denied)))
            else:
                print("{}")
        else:
            print(json.dumps({"continue": True, "error": "could not evaluate hook"}))


if __name__ == "__main__":
    main()
