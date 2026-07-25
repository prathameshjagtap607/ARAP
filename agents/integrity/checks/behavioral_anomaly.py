"""
Behavioral signal anomaly detection (M8-F04).
Deferred: requires voice/video session data (PRD §17).
When voice/video modalities ship, implement:
  - long pause detection
  - confidence mismatch between verbal and written responses
  - multi-speaker audio detection
All findings are flags for human review only — never automatic reject.
"""
import uuid

from agents.integrity.checks.ai_generated import FlagResult


def check_behavioral_anomalies(session_id: uuid.UUID, db) -> list[FlagResult]:
    return []
