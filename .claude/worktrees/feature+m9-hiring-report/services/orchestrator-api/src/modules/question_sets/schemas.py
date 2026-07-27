import uuid
from datetime import datetime

from pydantic import BaseModel


class QuestionItem(BaseModel):
    id: uuid.UUID
    sequence_no: int
    question: str
    category: str
    target_competencies: list[str]
    difficulty: str
    answer_format: str
    options: list[str] | None


class QuestionSetResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    generated_at: datetime
    locked_at: datetime
    generation_prompt_version: str
    questions: list[QuestionItem]
