"""Multi-provider LLM — Factory + Router."""

from app.ai.factory import LLMFactory
from app.ai.router import (
    LLMRouter,
    TASK_AGENT_SYNTH,
    TASK_AGENT_TOOL,
    TASK_ASPECT_GROUP,
    TASK_ASPECT_SUMMARY,
    TASK_EMBEDDING,
    TASK_REVIEW_SUMMARY,
    get_router,
    resolve,
)
from app.ai.service import AIService, get_ai_service

__all__ = [
    "AIService",
    "LLMFactory",
    "LLMRouter",
    "TASK_AGENT_SYNTH",
    "TASK_AGENT_TOOL",
    "TASK_ASPECT_GROUP",
    "TASK_ASPECT_SUMMARY",
    "TASK_EMBEDDING",
    "TASK_REVIEW_SUMMARY",
    "get_ai_service",
    "get_router",
    "resolve",
]
