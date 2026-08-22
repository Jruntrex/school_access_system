"""Daily attendance report sent to a Telegram chat via the Bot API.

Deliberately uses stdlib `urllib` instead of `requests` — the project has
no HTTP client dependency yet and this is a single POST, so it isn't worth
adding one (see requirements.txt).
"""

import json
import logging
import urllib.error
import urllib.request
from datetime import date as date_cls

from django.conf import settings

from school_access import selectors

logger = logging.getLogger("school_access")


class TelegramConfigError(Exception):
    """Raised when TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID are missing, or the
    Telegram API call itself fails."""


def build_report_rows(report_date: date_cls) -> tuple[list[dict], int]:
    """Клас/кількість присутніх учнів per class, plus the grand total."""
    class_rows = selectors.attendance_by_class(report_date)
    rows = [
        {"name": row["name"], "count": row["present_count"]}
        for row in class_rows
        if row["present_count"] > 0
    ]
    total = sum(row["count"] for row in rows)
    return rows, total


def format_report_text(report_date: date_cls, rows: list[dict], total: int) -> str:
    lines = [f"Звіт відвідуваності — {report_date.strftime('%d.%m.%Y')}", ""]
    if not rows:
        lines.append("Немає присутніх учнів.")
    else:
        for row in rows:
            lines.append(f"Клас - {row['name']}")
            lines.append(f"Кількість - {row['count']}")
    lines.append("")
    lines.append(f"Загалом: {total}")
    return "\n".join(lines)


def send_telegram_message(text: str) -> None:
    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_CHAT_ID
    if not token or not chat_id:
        raise TelegramConfigError(
            "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID не задані в .env"
        )

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    request = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status != 200:
                raise TelegramConfigError(
                    f"Telegram API повернув статус {response.status}"
                )
    except urllib.error.URLError as exc:
        raise TelegramConfigError(
            f"Не вдалось надіслати повідомлення в Telegram: {exc}"
        ) from exc


def send_daily_report(report_date: date_cls) -> str:
    """Builds and sends the report for `report_date`, returns the text sent."""
    rows, total = build_report_rows(report_date)
    text = format_report_text(report_date, rows, total)
    send_telegram_message(text)
    logger.info("Daily Telegram report sent for %s (%s students)", report_date, total)
    return text
