"""Shared schema bits."""
from pydantic import BaseModel


class Message(BaseModel):
    """Generic acknowledgement payload."""

    detail: str
