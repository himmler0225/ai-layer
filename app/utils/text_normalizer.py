from __future__ import annotations
import json

with open("normalization_dict.json") as f:
    DICT = json.load(f)

def normalize(text: str) -> str:
    tokens = text.lower().split()
    result = []
    for token in tokens:
        # Check 
        normalized = (
            DICT["teencode"].get(token) or
            DICT["vienglish"].get(token) or
            DICT["abbreviations"].get(token) or
            token  
        )
        result.append(normalized)
    return " ".join(result)

def detect_aspects(text: str) -> list[str]:
    found = []
    for aspect, keywords in DICT["aspects"].items():
        if any(kw in text for kw in keywords):
            found.append(aspect)
    return found