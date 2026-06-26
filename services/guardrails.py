"""
services/guardrails.py

Input and output guardrails for the CloudDash support system.

Input guardrails:
  - Prompt injection detection
  - Off-topic filtering

Output guardrails:
  - PII / API-key redaction
  - No-citation fallback enforcement (never fabricate CloudDash facts)
"""

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class InputGuardrailResult:
    safe: bool
    reason: str = ""
    sanitized_content: str = ""   # original content if safe, blocked message if not


@dataclass
class OutputGuardrailResult:
    content: str                  # final (possibly redacted) content
    redactions: list[str] = field(default_factory=list)
    citation_warning_added: bool = False


# ---------------------------------------------------------------------------
# Input guardrail
# ---------------------------------------------------------------------------

_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in [
        r"ignore\s+(previous|prior|all)\s+instructions?",
        r"reveal\s+(your\s+)?(system\s+prompt|instructions?|prompt)",
        r"bypass\s+(policy|rules?|restrictions?|guardrails?)",
        r"you\s+are\s+now\s+(a\s+)?(?!CloudDash)",   # "you are now a [other persona]"
        r"(act|pretend|behave)\s+as\s+if\s+you\s+(have\s+no|are\s+not)",
        r"disregard\s+(your\s+)?(previous|prior|all|safety)",
        r"(jailbreak|dan\s+mode|developer\s+mode)",
        r"print\s+(your\s+)?(system\s+prompt|instructions?)",
    ]
]

_OFF_TOPIC_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\b(write\s+me\s+a\s+(poem|song|story|essay))\b",
        r"\b(what\s+is\s+the\s+meaning\s+of\s+life)\b",
        r"\b(tell\s+me\s+a\s+joke)\b",
        r"\b(who\s+(is|was)\s+(the\s+)?(president|prime\s+minister))\b",
        r"\b(weather\s+(in|for|at))\b",
        r"\b(stock\s+price|cryptocurrency|bitcoin)\b",
        r"\b(write\s+(me\s+)?(a\s+)?(python|java|javascript|code|script))\b",
        r"\b(can\s+you\s+(code|program|build|create)\s+(me\s+)?(a\s+)?(script|app|tool|bot))\b",
        r"\b(how\s+to\s+(hack|scrape|crawl|bypass))\b",
    ]
]

_BLOCKED_INPUT_RESPONSE = (
    "I'm sorry, I can't process that request. "
    "I'm here to help with CloudDash support topics such as billing, "
    "technical issues, and account management."
)

_OFF_TOPIC_RESPONSE = (
    "That question seems outside my scope as a CloudDash support assistant. "
    "I can help with billing, technical issues, integrations, and account management. "
    "Is there something CloudDash-related I can assist you with?"
)


def check_input(content: str) -> InputGuardrailResult:
    """
    Validate a customer message before it reaches any agent.

    Returns InputGuardrailResult with safe=False if injection or off-topic
    patterns are detected. The caller should short-circuit and return the
    sanitized_content directly without invoking the orchestrator.
    """
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(content):
            logger.warning(
                "input_guardrail_blocked",
                extra={"reason": "prompt_injection", "pattern": pattern.pattern},
            )
            return InputGuardrailResult(
                safe=False,
                reason="prompt_injection",
                sanitized_content=_BLOCKED_INPUT_RESPONSE,
            )

    for pattern in _OFF_TOPIC_PATTERNS:
        if pattern.search(content):
            logger.info(
                "input_guardrail_blocked",
                extra={"reason": "off_topic", "pattern": pattern.pattern},
            )
            return InputGuardrailResult(
                safe=False,
                reason="off_topic",
                sanitized_content=_OFF_TOPIC_RESPONSE,
            )

    return InputGuardrailResult(safe=True, sanitized_content=content)


# ---------------------------------------------------------------------------
# Output guardrail
# ---------------------------------------------------------------------------

# Matches things that look like API keys, tokens, or secrets
_PII_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("email", re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")),
    ("api_key", re.compile(r"\b(sk|pk|api|key|token)[-_][a-zA-Z0-9]{16,}\b", re.IGNORECASE)),
    ("aws_key", re.compile(r"\b(AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("generic_secret", re.compile(r"\b[a-zA-Z0-9]{32,}\b")),  # long random strings
    ("credit_card", re.compile(r"\b(?:\d[ -]?){13,16}\b")),
]

_NO_CITATION_FALLBACK = (
    "\n\n---\n"
    "Note: I was unable to find a CloudDash knowledge base article to support this answer. "
    "To ensure accuracy, I recommend escalating this to a human specialist "
    "who can verify against official CloudDash documentation."
)

# Topics where we must have KB citations — never fabricate
_CITATION_REQUIRED_TOPICS = [
    "price", "pricing", "cost", "plan", "upgrade", "downgrade",
    "refund", "invoice", "charge", "policy", "feature", "limit",
    "rate limit", "quota", "sla", "uptime", "guarantee",
]


def check_output(content: str, citations: list, original_message: str = "") -> OutputGuardrailResult:
    """
    Sanitize agent output before returning to the customer.

    1. Redact PII / API-key-like values.
    2. If the response touches pricing/policy topics but has no KB citations,
       append a transparency notice rather than silently returning ungrounded claims.
    """
    redacted_content = content
    redactions: list[str] = []

    for label, pattern in _PII_PATTERNS:
        matches = pattern.findall(redacted_content)
        if matches:
            redacted_content = pattern.sub(f"[REDACTED-{label.upper()}]", redacted_content)
            redactions.extend([label] * len(matches))
            logger.warning(
                "output_guardrail_redaction",
                extra={"type": label, "count": len(matches)},
            )

    # Citation enforcement for sensitive topics
    citation_warning_added = False
    needs_citation = _touches_citation_required_topic(content, original_message)
    if needs_citation and not citations:
        redacted_content += _NO_CITATION_FALLBACK
        citation_warning_added = True
        logger.warning(
            "output_guardrail_no_citation",
            extra={"topic_detected": True, "citations_present": False},
        )

    return OutputGuardrailResult(
        content=redacted_content,
        redactions=redactions,
        citation_warning_added=citation_warning_added,
    )


def _touches_citation_required_topic(content: str, original_message: str) -> bool:
    combined = (content + " " + original_message).lower()
    return any(topic in combined for topic in _CITATION_REQUIRED_TOPICS)