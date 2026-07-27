"""
Add the repo root (parent of agents/) to sys.path so that
`from agents.*` imports resolve when running pytest from the agents/ directory.
"""
import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))
