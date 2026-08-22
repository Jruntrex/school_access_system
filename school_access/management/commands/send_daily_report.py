"""Sends the daily Telegram attendance report once the admin-configured
time (see /settings/) has passed for today.

Not itself a scheduler — intended to be invoked every few minutes by an
external trigger (Windows Task Scheduler; see README) and to no-op until
it's actually time, then send exactly once per day.

Usage:
    python manage.py send_daily_report
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from school_access.models import DailyReportSettings
from school_access.services.telegram_report import TelegramConfigError, send_daily_report


class Command(BaseCommand):
    help = "Send the daily Telegram attendance report if the configured time has passed"

    def handle(self, *args, **options):
        report_settings = DailyReportSettings.load()

        if not report_settings.is_enabled:
            self.stdout.write("Щоденний звіт вимкнено в налаштуваннях.")
            return

        now = timezone.localtime()
        today = now.date()

        if report_settings.last_sent_on == today:
            self.stdout.write("Звіт за сьогодні вже надіслано.")
            return

        if now.time() < report_settings.send_time:
            self.stdout.write(
                f"Ще не час: зараз {now:%H:%M}, звіт заплановано на "
                f"{report_settings.send_time:%H:%M}."
            )
            return

        try:
            send_daily_report(today)
        except TelegramConfigError as exc:
            self.stderr.write(self.style.ERROR(str(exc)))
            return

        report_settings.last_sent_on = today
        report_settings.save(update_fields=["last_sent_on"])
        self.stdout.write(self.style.SUCCESS(f"Звіт за {today} надіслано в Telegram."))
