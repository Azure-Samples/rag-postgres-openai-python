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
