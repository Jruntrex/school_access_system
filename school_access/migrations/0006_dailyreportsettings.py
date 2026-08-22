import datetime

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("school_access", "0005_attendancedaily_last_entry_event_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="DailyReportSettings",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "send_time",
                    models.TimeField(default=datetime.time(16, 0)),
                ),
                ("is_enabled", models.BooleanField(default=True)),
                ("last_sent_on", models.DateField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": '"school_access"."daily_report_settings"',
            },
        ),
    ]
