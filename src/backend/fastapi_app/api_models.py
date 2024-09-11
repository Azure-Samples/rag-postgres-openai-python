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


class RetrievalMode(str, Enum):
    TEXT = "text"
    VECTORS = "vectors"
    HYBRID = "hybrid"


class ChatRequestOverrides(BaseModel):
    top: int = 3
    temperature: float = 0.3
    retrieval_mode: RetrievalMode = RetrievalMode.HYBRID
    use_advanced_flow: bool = True
    prompt_template: str | None = None


class ChatRequestContext(BaseModel):
    overrides: ChatRequestOverrides


class ChatRequest(BaseModel):
    messages: list[ChatCompletionMessageParam]
    context: ChatRequestContext
    sessionState: Any | None = None


class ThoughtStep(BaseModel):
    title: str
    description: Any
    props: dict = {}


class RAGContext(BaseModel):
    data_points: dict[str, dict[str, Any]]
    thoughts: list[ThoughtStep]
    followup_questions: list[str] | None = None


class RetrievalResponse(BaseModel):
    message: Message
    context: RAGContext
    sessionState: Any | None = None


class RetrievalResponseDelta(BaseModel):
    delta: Message | None = None
    context: RAGContext | None = None
    sessionState: Any | None = None


class ItemPublic(BaseModel):
    # This should match postgres_models.py
    id: str
    title: str
    description: str
    speakers: list[str]
    tracks: list[str]
    day: str
    time: str
    mode: str


class ItemWithDistance(ItemPublic):
    distance: float


class ChatParams(ChatRequestOverrides):
    prompt_template: str
    response_token_limit: int = 1024
    enable_text_search: bool
    enable_vector_search: bool
    original_user_query: str
    past_messages: list[ChatCompletionMessageParam]
