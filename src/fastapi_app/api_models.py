from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel


class Message(BaseModel):
    content: str
    role: str = "user"


class ChatRequest(BaseModel):
    messages: list[Message]
    context: dict = {}


class ThoughtStep(BaseModel):
    title: str
    description: Any
    props: dict = {}


@dataclass
class RAGContext:
    data_points: dict[int, dict[str, Any]]
    thoughts: list[ThoughtStep]
    followup_questions: list[str] | None = None


@dataclass
class RetrievalResponse:
    message: Message
    context: RAGContext
    session_state: Any | None = None
