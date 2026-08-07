from app.rag.movie_hint import context_for_filtering, current_question, has_movie_context, wants_catalog, wants_review
from app.services.agent.domains import DOMAINS, DOMAIN_IDS

# Derived from DOMAINS instead of hard-coding domain names — adding/removing a
# domain only requires editing domains.py, and the lists below update automatically.
_REVIEW_DOMAIN_IDS = [d["id"] for d in DOMAINS if "review" in d.get("capabilities", ())]
_CATALOG_DOMAIN_IDS = [d["id"] for d in DOMAINS if "catalog" in d.get("capabilities", ())]
_MENTION_PATTERNS = [(d["id"], d["mention_re"]) for d in DOMAINS if d.get("mention_re")]


def _mentioned_domains(text: str) -> list[str]:
    """Which domains are directly named in the text (e.g. 'youtube', 'tiktok')."""
    return [domain_id for domain_id, pattern in _MENTION_PATTERNS if pattern.search(text)]


def classify_workers_deterministic(task: str, requested_tool_set: str) -> list[str] | None:
    if requested_tool_set in DOMAIN_IDS:
        return [requested_tool_set]

    ctx_text = context_for_filtering(task)
    question = current_question(task)
    mentioned = _mentioned_domains(ctx_text)

    wants_catalog_intent = wants_catalog(ctx_text) or wants_catalog(question)
    wants_review_intent = wants_review(ctx_text) or wants_review(question) or has_movie_context(task)

    if len(mentioned) >= 2:
        return mentioned + (_CATALOG_DOMAIN_IDS if wants_catalog_intent else [])
    if len(mentioned) == 1:
        return mentioned
    if wants_catalog_intent:
        return _CATALOG_DOMAIN_IDS or None
    if wants_review_intent and _REVIEW_DOMAIN_IDS:
        return [_REVIEW_DOMAIN_IDS[0]]
    return None
