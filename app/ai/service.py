"""High-level AI service — facade cho business logic."""

from __future__ import annotations

from app.ai.router import (TASK_ASPECT_GROUP, TASK_ASPECT_SUMMARY,
                           TASK_REVIEW_SUMMARY, LLMRouter, get_router)


class AIService:
    def __init__(self, router: LLMRouter | None = None):
        self._router = router or get_router()

    async def group_aspects(
        self, *, prompt: str, system: str, max_tokens: int | None = None
    ) -> str:
        return await self._router.complete_json(
            TASK_ASPECT_GROUP,
            user_prompt=prompt,
            system_prompt=system,
            max_tokens=max_tokens,
        )

    async def summarize_aspect(
        self, *, prompt: str, system: str, max_tokens: int | None = None
    ) -> str:
        return await self._router.complete_json(
            TASK_ASPECT_SUMMARY,
            user_prompt=prompt,
            system_prompt=system,
            max_tokens=max_tokens,
        )

    async def summarize_review(
        self, *, prompt: str, system: str, max_tokens: int | None = None
    ) -> str:
        return await self._router.complete(
            TASK_REVIEW_SUMMARY,
            user_prompt=prompt,
            system_prompt=system,
            max_tokens=max_tokens,
        )


def get_ai_service() -> AIService:
    return AIService()
