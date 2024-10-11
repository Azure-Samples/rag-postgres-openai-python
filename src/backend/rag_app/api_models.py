from enum import Enum
from typing import Any

from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel


class AIChatRoles(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Message(BaseModel):
    content: str
    role: AIChatRoles = AIChatRoles.USER


class ChatRequest(BaseModel):
    messages: list[ChatCompletionMessageParam]


class RAGContext(BaseModel):
    data_points: dict[int, dict[str, Any]]
    followup_questions: list[str] | None = None

class RetrievalResponse(BaseModel):
    message: Message
    context: RAGContext
    sessionState: Any | None = None
