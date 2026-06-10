"""
Rule-based sentiment classifier using normalization_dict.json.
Handles Vietnamese teencode, vienglish, abbreviations before scoring.
"""
import json
import re
from pathlib import Path
from typing import Dict, List

_DICT_PATH = Path(__file__).parent.parent / "data" / "normalization_dict.json"
with open(_DICT_PATH, encoding="utf-8") as _f:
    _D = json.load(_f)

_TEENCODE    = _D["teencode"]
_VIENGLISH   = _D["vienglish"]
_ABBREV      = _D["abbreviations"]
_SENTIMENTS  = _D["sentiment_indicators"]
_ASPECTS     = _D["aspects"]

# Pre-build combined replacement map (longest key first to avoid partial matches)
_NORM_MAP = {**_ABBREV, **_VIENGLISH, **_TEENCODE}
_NORM_PAIRS = sorted(_NORM_MAP.items(), key=lambda x: -len(x[0]))


def _normalize(text: str) -> str:
    t = text.lower().strip()
    for src, dst in _NORM_PAIRS:
        t = re.sub(r"(?<![a-zA-ZÀ-ỹ])" + re.escape(src) + r"(?![a-zA-ZÀ-ỹ])", dst, t)
    return t


def classify_sentiment(text: str) -> str:
    t = _normalize(text)
    pos = sum(1 for w in _SENTIMENTS["positive"] if w in t)
    neg = sum(1 for w in _SENTIMENTS["negative"] if w in t)
    neu = sum(1 for w in _SENTIMENTS["neutral"]  if w in t)
    if neg > pos:
        return "negative"
    if pos > neg:
        return "positive"
    if neu > 0:
        return "neutral"
    return "neutral"


def detect_aspects(text: str) -> List[str]:
    t = _normalize(text)
    return [asp for asp, kws in _ASPECTS.items() if any(kw in t for kw in kws)]


def analyze_reviews(reviews: List[Dict]) -> Dict:
    """
    Classify a list of review dicts and return a structured breakdown.

    Input review fields (any of): content, comment, text
    Optional fields: rating, stars, source_url
    """
    buckets: Dict[str, List[Dict]] = {"positive": [], "negative": [], "neutral": []}
    aspect_scores: Dict[str, Dict[str, int]] = {
        asp: {"positive": 0, "negative": 0, "neutral": 0}
        for asp in _ASPECTS
    }

    for r in reviews:
        text = r.get("content") or r.get("comment") or r.get("text") or ""
        if not text:
            continue

        sentiment = classify_sentiment(text)
        aspects   = detect_aspects(text)

        entry = {
            "text":     text[:300],
            "aspects":  aspects,
            "rating":   r.get("rating") or r.get("stars"),
            "source":   r.get("source_url") or r.get("url"),
        }
        buckets[sentiment].append(entry)

        for asp in aspects:
            if asp in aspect_scores:
                aspect_scores[asp][sentiment] += 1

    total = sum(len(v) for v in buckets.values())
    return {
        "total_analyzed": total,
        "summary": {
            "positive": len(buckets["positive"]),
            "negative": len(buckets["negative"]),
            "neutral":  len(buckets["neutral"]),
            "positive_pct": round(len(buckets["positive"]) / total * 100, 1) if total else 0,
            "negative_pct": round(len(buckets["negative"]) / total * 100, 1) if total else 0,
        },
        "aspect_scores": aspect_scores,
        "samples": {
            "positive": buckets["positive"][:5],
            "negative": buckets["negative"][:5],
            "neutral":  buckets["neutral"][:3],
        },
    }
