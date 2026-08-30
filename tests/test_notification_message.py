from __future__ import annotations

from stock_radar.notification.message import SBI_CHECK_ITEMS, build_notification_message


def test_message_contains_required_fields():
    message = build_notification_message(
        ticker="4840",
        company_name="サンプル銘柄A",
        title="業績予想の上方修正に関するお知らせ",
        category="A",
        notification_rank="S",
        total_score=80,
    )
    assert "4840" in message.subject
    assert "サンプル銘柄A" in message.subject
    assert "S" in message.subject
    assert "業績予想の上方修正に関するお知らせ" in message.body
    assert "A" in message.body
    assert "80" in message.body


def test_message_lists_only_sbi_field_names_not_values():
    """spec §13 rule 6: never scrape/display actual SBI values, only the
    human-facing field names to check."""
    message = build_notification_message(
        ticker="4840", company_name="サンプル銘柄A", title="お知らせ",
        category="A", notification_rank="A", total_score=60,
    )
    for item in SBI_CHECK_ITEMS:
        assert item in message.body
    assert "自動ログイン" not in message.body or "行いません" in message.body


def test_message_handles_missing_category():
    message = build_notification_message(
        ticker="3907", company_name="サンプル銘柄D", title="お知らせ",
        category=None, notification_rank="A", total_score=65,
    )
    assert "(分類なし)" in message.body
