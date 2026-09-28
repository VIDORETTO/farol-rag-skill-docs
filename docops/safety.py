"""Deterministic content-safety classification for untrusted source text.

Sources are data, never instructions. This module flags text that tries to
steer the reading agent so extraction, indexing, MCP answers and skill
synthesis can keep it out of evidence or mark it. It is a conservative,
pattern-based layer, not a guarantee: see SECURITY.md for its limits.

Risk levels:

- ``high``: a directive aimed at the reading AI (override instructions, adopt a
  new role, reveal secrets, exfiltrate data, invoke tools);
- ``suspicious``: prompt-like or hidden text that is legitimate in context
  (papers quoting prompts, docs about system messages, invisible Unicode) but
  must be visible to the reader;
- ``none``: ordinary content.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

_I = re.IGNORECASE

_HIGH: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "override_instructions",
        re.compile(
            r"\b(?:ignore|disregard|forget|override)\s+(?:all\s+|any\s+|the\s+|your\s+)?"
            r"(?:previous|prior|above|earlier|system|preceding)\s+(?:instructions?|prompts?|rules|messages?)",
            _I,
        ),
    ),
    (
        "override_instructions",
        re.compile(r"\bignore\s+(?:todas\s+as\s+)?(?:as\s+)?instru[çc][õo]es\s+anteriores\b", _I),
    ),
    (
        "role_hijack",
        re.compile(
            r"\b(?:(?:you\s+are\s+now|from\s+now\s+on\s+you\s+are)\s+(?:an?\s+|in\s+)?(?:\w+\s+){0,3}"
            r"(?:ai|assistant|agent|model|bot|persona|mode|dan)\b|act\s+as\s+an?\s+unrestricted|developer\s+mode)\b",
            _I,
        ),
    ),
    (
        "secret_disclosure",
        re.compile(
            r"\b(?:reveal|show|print|leak|output|dump|revele|mostre)\s+(?:the\s+|your\s+|a\s+|o\s+)?"
            r"(?:secret|credential|api\s*key|password|token|senha|segredo)s?",
            _I,
        ),
    ),
    (
        "exfiltration",
        re.compile(
            r"\b(?:send|post|upload|forward|exfiltrate|envie)\b[^.\n]{0,80}"
            r"(?:conversation|history|context|memory|data|files?|conversa)[^.\n]{0,80}https?://",
            _I,
        ),
    ),
    (
        "tool_invocation",
        re.compile(
            r"\b(?:ai|assistant|agent|llm|model)s?\b[^.\n]{0,60}\b(?:must|should|shall)\s+"
            r"(?:call|invoke|run|execute)\b[^.\n]{0,40}\b(?:tool|function|command)",
            _I,
        ),
    ),
)

_SUSPICIOUS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("prompt_directive", re.compile(r"\bdo\s+not\s+(?:tell|mention|disclose|reveal)\b", _I)),
    ("system_prompt_reference", re.compile(r"\bsystem\s+(?:message|prompt)\b", _I)),
)

_HIDDEN_CATEGORIES = frozenset({"Cf"})
_BIDI_OVERRIDES = frozenset("‪‫‬‭‮⁦⁧⁨⁩")
_ALLOWED_FORMAT = frozenset({"­", "﻿"})


@dataclass(frozen=True)
class SafetyVerdict:
    risk: str
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {"risk": self.risk, "reasons": list(self.reasons)}


def _hidden_reasons(text: str) -> list[str]:
    reasons: list[str] = []
    if any(char in _BIDI_OVERRIDES for char in text):
        reasons.append("bidi_override")
    if any(0xE0000 <= ord(char) <= 0xE007F for char in text):
        reasons.append("unicode_tag_characters")
    invisible = sum(
        1
        for char in text
        if unicodedata.category(char) in _HIDDEN_CATEGORIES
        and char not in _BIDI_OVERRIDES
        and char not in _ALLOWED_FORMAT
        and not 0xE0000 <= ord(char) <= 0xE007F
    )
    if invisible >= 2:
        reasons.append("invisible_characters")
    return reasons


def classify(text: str) -> SafetyVerdict:
    """Classify one block or paragraph of untrusted text."""

    if not text:
        return SafetyVerdict("none")
    high = sorted({name for name, pattern in _HIGH if pattern.search(text)})
    if high:
        return SafetyVerdict("high", high)
    suspicious = sorted({name for name, pattern in _SUSPICIOUS if pattern.search(text)} | set(_hidden_reasons(text)))
    if suspicious:
        return SafetyVerdict("suspicious", suspicious)
    return SafetyVerdict("none")


def dominated_by_high_risk(paragraphs: list[str]) -> bool:
    """True when high-risk text dominates a document rather than appearing in it.

    A paper or guide that quotes an attack keeps its other evidence; a document
    whose substance is the attack is quarantined as a whole.
    """

    substantive = [paragraph for paragraph in paragraphs if re.search(r"\w{3,}", paragraph)]
    if not substantive:
        return False
    risky = sum(1 for paragraph in substantive if classify(paragraph).risk == "high")
    return risky > 0 and risky / len(substantive) >= 0.25
