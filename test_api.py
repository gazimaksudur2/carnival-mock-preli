"""Unit tests for the classifier.

Covers the 5 sample cases from the spec plus a couple of edge cases:
  - severity bumping via URGENCY_BOOSTERS
  - Bengali keyword match
  - safety: summary must never echo raw message text (PIN/OTP/password)
"""

from classifier import build_summary, classify


def test_sample_1_wrong_transfer():
    r = classify("sent 3000 to wrong number")
    assert r["case_type"] == "wrong_transfer"
    assert r["severity"] == "high"
    assert r["department"] == "dispute_resolution"


def test_sample_2_payment_failed():
    r = classify("Payment failed but balance deducted")
    assert r["case_type"] == "payment_failed"
    assert r["severity"] == "high"
    assert r["department"] == "payments_ops"


def test_sample_3_phishing():
    r = classify("Someone called asking my OTP")
    assert r["case_type"] == "phishing_or_social_engineering"
    assert r["severity"] == "critical"
    assert r["department"] == "fraud_risk"
    assert r["human_review_required"] is True


def test_sample_4_refund_request():
    r = classify("Please refund my last transaction")
    assert r["case_type"] == "refund_request"
    assert r["severity"] == "low"
    assert r["department"] == "customer_support"


def test_sample_5_other():
    r = classify("App crashed when I opened it")
    assert r["case_type"] == "other"
    assert r["severity"] == "low"
    assert r["department"] == "customer_support"


def test_urgency_booster_bumps_severity():
    # refund_request is normally low; an urgency word bumps it to medium.
    r = classify("I urgently need a refund please")
    assert r["case_type"] == "refund_request"
    assert r["severity"] == "medium"


def test_bengali_keyword_matches():
    r = classify("আমি ভুল নম্বরে টাকা পাঠিয়েছি")
    assert r["case_type"] == "wrong_transfer"


def test_summary_never_echoes_raw_message():
    msg = "my pin is 1234 and my otp is 5678 please help"
    r = classify(msg)
    assert "1234" not in r["agent_summary"]
    assert "5678" not in r["agent_summary"]
    # Built from template only:
    assert r["agent_summary"] == build_summary(r["case_type"], msg)


def test_human_review_only_for_critical_or_phishing():
    # Other / non-urgent -> no human review.
    assert classify("App crashed")["human_review_required"] is False
    # Phishing case -> always requires human review.
    assert classify("Someone asked for my password")["human_review_required"] is True
    # Urgency on a non-phishing case bumps severity but does NOT auto-trigger
    # human review on its own — that's reserved for phishing/critical.
    r = classify("urgent: refund my last transaction please")
    assert r["human_review_required"] is False
    assert r["severity"] == "medium"  # low -> medium via urgency bump


def test_confidence_in_valid_range():
    for msg in [
        "wrong number",
        "Payment failed but balance deducted",
        "Someone called asking my OTP",
        "refund please",
        "App crashed",
    ]:
        c = classify(msg)["confidence"]
        assert 0.0 <= c <= 1.0


if __name__ == "__main__":
    import sys
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))