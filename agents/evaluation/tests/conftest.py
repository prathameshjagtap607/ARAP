"""
Ensure services/orchestrator-api is on sys.path so that
`from src.models.*` imports inside pipeline.py resolve during testing.
"""
import sys
from pathlib import Path

_orchestrator = Path(__file__).resolve().parents[3] / "services" / "orchestrator-api"
if str(_orchestrator) not in sys.path:
    sys.path.insert(0, str(_orchestrator))
