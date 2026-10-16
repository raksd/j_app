from __future__ import annotations

import re

BANNED_PHRASES = [
    "spearhead", "leverag", "synerg", "results-driven", "results driven", "dynamic",
    "passionate", "proven track record", "proven ability", "cutting-edge", "cutting edge",
    "seamless", "robust", "game-changing", "game changer", "best-in-class", "world-class",
    "go-getter", "self-starter", "team player", "think outside the box", "thought leader",
    "holistic", "streamline", "utilis", "utiliz", "delve", "tapestry", "testament to",
    "in today's fast-paced", "fast-paced",
]

FIRST_PERSON = re.compile(r"\b(I|me|my|mine|I'm|I've)\b")


def find_banned(text: str) -> list[str]:
    low = text.lower()
    found = [p for p in BANNED_PHRASES if p in low]
    if FIRST_PERSON.search(text):
        found.append("first person")
    return found


LETTER_CLICHES = [
    "i am writing to apply", "i am writing to express", "excited to bring", "i am excited",
    "i am thrilled", "i would be a great fit", "perfect fit", "unique blend", "wealth of experience",
    "hit the ground running", "add value", "bring to the table", "look forward to the opportunity",
]


def find_letter_banned(text: str) -> list[str]:
    """Banned wording for cover letters. First person is natural there, so it is not flagged."""
    low = text.lower()
    return [p for p in [*BANNED_PHRASES, *LETTER_CLICHES] if p in low]


def shared_openers(bullets: list[str]) -> bool:
    firsts = [b.split()[0].lower() for b in bullets if b.split()]
    return len(firsts) >= 4 and len(set(firsts)) <= max(1, len(firsts) // 3)
