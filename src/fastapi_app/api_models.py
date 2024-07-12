from typing import Any

from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel


class Message(BaseModel):
    content: str
    role: str = "user"


class ChatRequest(BaseModel):
    messages: list[ChatCompletionMessageParam]
    context: dict = {}


class ThoughtStep(BaseModel):
    title: str
    description: Any
    props: dict = {}


class RAGContext(BaseModel):
    data_points: dict[int, dict[str, Any]]
    thoughts: list[ThoughtStep]
    followup_questions: list[str] | None = None


class RetrievalResponse(BaseModel):
    message: Message
    context: RAGContext
    session_state: Any | None = None
