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


class RetrievalResponseDelta(BaseModel):
    delta: Message | None = None
    context: RAGContext | None = None
    session_state: Any | None = None


class ItemPublic(BaseModel):
    id: int
    type: str
    brand: str
    name: str
    description: str
    price: float


class ItemWithDistance(ItemPublic):
    distance: float
