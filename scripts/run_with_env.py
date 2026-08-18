"""Run a command with a .env file loaded into its environment.

Exists because `bash -c "set -a; source .env; ..."` breaks on any value
containing spaces (e.g. a Gmail app password like SMTP_PASSWORD) — bash
word-splits the unquoted value and silently drops everything after the
first word, so the app starts with a truncated/empty secret and fails
authentication with no obvious cause. This script parses KEY=VALUE lines
directly in Python, so spaces in values are preserved correctly.

Usage:
    python scripts/run_with_env.py <path-to-.env> <command> [args...]

Example (from repo root):
    python scripts/run_with_env.py services/orchestrator-api/.env \\
        python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 \\
        --app-dir services/orchestrator-api
"""

import os
import sys


def load_dotenv(path: str) -> None:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.lstrip().startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            os.environ[key] = value


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    env_path = sys.argv[1]
    cmd = sys.argv[2:]
    load_dotenv(env_path)
    os.execvp(cmd[0], cmd)
