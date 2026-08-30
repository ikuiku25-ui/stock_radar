"""Notification content (spec §11, §13 rule 6).

Only human-facing FIELD NAMES for the SBI-side check are included in the
message — never actual values (current price, quote, buying power). Stock
Radar never logs into or scrapes a brokerage; the human looks those values
up themselves. This is a hard rule (spec §13 rule 6), not a preference.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

SBI_CHECK_ITEMS = ("現在値", "気配値", "投資可能額")


@dataclass
class NotificationMessage:
    subject: str
    body: str


def build_notification_message(
    ticker: str,
    company_name: str,
    title: str,
    category: Optional[str],
    notification_rank: str,
    total_score: int,
) -> NotificationMessage:
    subject = f"[Stock Radar] {notification_rank}ランク検知: {ticker} {company_name}"
    category_str = category or "(分類なし)"
    check_items = "、".join(SBI_CHECK_ITEMS)
    body = (
        f"銘柄コード: {ticker}\n"
        f"会社名: {company_name}\n"
        f"検知した材料: {title}\n"
        f"カテゴリ: {category_str}\n"
        f"ランク: {notification_rank}（total_score={total_score}）\n"
        "\n"
        f"証券会社サイトで確認してください: {check_items}\n"
        "(Stock Radarは自動ログイン・自動取得を行いません)\n"
    )
    return NotificationMessage(subject=subject, body=body)
