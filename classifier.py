"""Rule-based ticket classifier for finance support messages.

Categories: wrong_transfer, payment_failed, phishing_or_social_engineering,
refund_request, other.

Scoring: each keyword match adds the category weight. The highest-scoring
category wins. With no matches the case falls back to "other".

Severity: starts from SEVERITY_MAP, then bumps up one level if any
URGENCY_BOOSTER appears (unless already critical).

The summary is built from SUMMARY_TEMPLATES only — the raw user message is
never echoed back, so sensitive tokens (OTP / PIN / password) can never leak.
"""

from __future__ import annotations

PATTERNS: dict[str, dict] = {
    "wrong_transfer": {
        "keywords": [
            "wrong number", "wrong account", "wrong recipient",
            "sent to wrong", "mistaken transfer", "wrong person",
            "ভুল নম্বর", "ভুল একাউন্ট",  # Bengali support
        ],
        "weight": 10,
    },
    "payment_failed": {
        "keywords": [
            "payment failed", "transaction failed", "failed but",
            "balance deducted", "money deducted", "charged but",
            "not received", "debited but", "cut from account",
            "পেমেন্ট ফেইল", "টাকা কাটা গেছে",
        ],
        "weight": 10,
    },
    "phishing_or_social_engineering": {
        "keywords": [
            "otp", "pin", "password", "asked for", "someone called",
            "called me", "sms came", "asking my", "share my",
            "bkash call", "nagad call", "verify account",
            "suspicious", "scam", "fraud call", "fake",
            "ওটিপি", "পিন", "পাসওয়ার্ড",
        ],
        "weight": 10,
    },
    "refund_request": {
        "keywords": [
            "refund", "money back", "return my", "give back",
            "cancel order", "changed my mind", "want back",
            "রিফান্ড", "ফেরত",
        ],
        "weight": 10,
    },
}

SEVERITY_MAP: dict[str, str] = {
    "wrong_transfer":                 "high",
    "payment_failed":                 "high",
    "phishing_or_social_engineering": "critical",
    "refund_request":                 "low",
    "other":                          "low",
}

# Bump severity if these urgency words appear.
URGENCY_BOOSTERS: list[str] = [
    "urgent", "immediately", "right now", "emergency",
    "all my money", "life savings", "large amount",
    "জরুরি", "এখনই",
]

DEPARTMENT_MAP: dict[str, str] = {
    "wrong_transfer":                 "dispute_resolution",
    "payment_failed":                 "payments_ops",
    "phishing_or_social_engineering": "fraud_risk",
    "refund_request":                 "customer_support",
    "other":                          "customer_support",
}

# Safe summaries — never derived from the raw user message, so PIN/OTP/password
# words can never be echoed back to the agent or downstream systems.
SUMMARY_TEMPLATES: dict[str, str] = {
    "wrong_transfer": (
        "Customer reports sending money to an unintended recipient and is "
        "requesting recovery assistance."
    ),
    "payment_failed": (
        "Customer reports a failed transaction and is concerned their balance "
        "may have been affected."
    ),
    "phishing_or_social_engineering": (
        "Customer reports a suspicious contact and may be targeted by a "
        "social engineering attempt."
    ),
    "refund_request": "Customer is requesting a refund for a recent transaction.",
    "other": "Customer has submitted a support request that requires agent review.",
}


def build_summary(case_type: str, original_message: str) -> str:
    """Return the safe template summary for a case type.

    `original_message` is accepted for API symmetry but intentionally unused —
    we must never echo raw user text in the summary.
    """
    return SUMMARY_TEMPLATES.get(case_type, SUMMARY_TEMPLATES["other"])


def classify(message: str) -> dict:
    """Classify a free-text support message.

    Returns a dict with keys: case_type, severity, department, agent_summary,
    human_review_required, confidence.
    """
    text = (message or "").lower().strip()

    # Score each category by summing the weight of every keyword that appears.
    scores: dict[str, int] = {case: 0 for case in PATTERNS}
    for case, config in PATTERNS.items():
        for keyword in config["keywords"]:
            if keyword and keyword in text:
                scores[case] += config["weight"]

    best_case = max(scores, key=scores.get)
    best_score = scores[best_case]

    # Fall back to "other" if nothing matched.
    if best_score == 0:
        best_case = "other"

    # Confidence: normalize on number of distinct keywords that hit (cap at 0.97).
    matched_keywords = PATTERNS.get(best_case, {}).get("keywords", [])
    matched_count = sum(1 for kw in matched_keywords if kw in text)
    if best_case == "other":
        confidence = 0.5
    else:
        confidence = min(0.5 + (matched_count * 0.15), 0.97)

    # Severity — start from map, then bump up one level on urgency words.
    severity = SEVERITY_MAP[best_case]
    if severity != "critical":
        if any(word in text for word in URGENCY_BOOSTERS):
            bump = {"low": "medium", "medium": "high", "high": "critical"}
            severity = bump.get(severity, severity)

    department = DEPARTMENT_MAP[best_case]
    human_review = severity == "critical" or best_case == "phishing_or_social_engineering"

    return {
        "case_type":             best_case,
        "severity":              severity,
        "department":            department,
        "agent_summary":         build_summary(best_case, message),
        "human_review_required": human_review,
        "confidence":            round(confidence, 2),
    }


if __name__ == "__main__":
    # Quick CLI sanity check.
    samples = [
        "sent 3000 to wrong number",
        "Payment failed but balance deducted",
        "Someone called asking my OTP",
        "Please refund my last transaction",
        "App crashed when I opened it",
    ]
    for s in samples:
        print(f"{s!r}\n  -> {classify(s)}\n")