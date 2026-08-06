"""Seed a demo academic year, classes, students, RFID cards and access
events for manual testing (see README "Верифікація/тести"). Reuses the
same services the UI/API call, so seeded data respects the same
invariants (one active class/meal/card assignment per student, etc.).

Usage:
    python manage.py seed_demo_data
"""

from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from school_access.models import AcademicYear, RfidReader, Student
from school_access.services import card_assignment
from school_access.services import events as events_service
from school_access.services.imports import ImportRow, import_students

DEMO_STUDENTS = [
    # (last_name, first_name, class_name, meal_option_code)
    ("Іваненко", "Іван", "5-А", "STANDARD"),
    ("Петренко", "Марія", "5-А", "NO_MEAL"),
    ("Сидоренко", "Олег", "5-А", "STANDARD"),
    ("Коваленко", "Анна", "5-А", "SPECIAL"),
    ("Бондаренко", "Максим", "5-Б", "STANDARD"),
    ("Мельник", "Софія", "5-Б", "STANDARD"),
    ("Ткаченко", "Артем", "5-Б", "NO_MEAL"),
    ("Кравченко", "Валерія", "5-Б", "STANDARD"),
    ("Шевченко", "Дмитро", "6-А", "STANDARD"),
    ("Олійник", "Катерина", "6-А", "SPECIAL"),
    ("Гончаренко", "Назар", "6-А", "STANDARD"),
    ("Павленко", "Юлія", "6-А", "NO_MEAL"),
]

# Fake but well-formed UIDs, same shape as a real PN532 4-byte UID hex string.
DEMO_CARD_UIDS = ["04A1B2C3D4", "04A1B2C3D5", "04A1B2C3D6", "04A1B2C3D7"]


class Command(BaseCommand):
    help = "Seed demo academic year/classes/students/cards/events for manual testing"

    def handle(self, *args, **options):
        if Student.objects.exists():
            self.stdout.write(
                self.style.WARNING(
                    "Students already exist — skipping so demo data isn't duplicated. "
                    "Wipe them first (e.g. via /admin/) if you want a fresh seed."
                )
            )
            return

        academic_year, _ = AcademicYear.objects.get_or_create(
            name="2026/2027",
            defaults={
                "starts_on": date(2026, 9, 1),
                "ends_on": date(2027, 6, 30),
                "is_active": True,
            },
        )

        rows = [
            ImportRow(last_name=ln, first_name=fn, class_name=cn, meal_option_code=mo)
            for ln, fn, cn, mo in DEMO_STUDENTS
        ]
        result = import_students(rows, academic_year)
        self.stdout.write(self.style.SUCCESS(f"Created {result.created_students} students"))
        for error in result.errors:
            self.stdout.write(self.style.WARNING(error))

        students = list(Student.objects.order_by("id"))
        carded_students = students[: len(DEMO_CARD_UIDS)]
        for student, uid in zip(carded_students, DEMO_CARD_UIDS):
            card_assignment.assign_card(uid, student)
            self.stdout.write(f"  card {uid} -> #{student.id} {student}")

        reader = RfidReader.objects.filter(code="VESTIBULE_ENTRY_1").first()
        if reader is not None and students:
            now = timezone.now()

            # A valid entry scan this morning for the first card holder.
            events_service.process_scan_event(
                DEMO_CARD_UIDS[0], reader.code, event_time=now - timedelta(hours=2)
            )

            # A manual guard entry for a student with no card.
            no_card_student = next(
                (s for s in students if s not in carded_students), None
            )
            if no_card_student:
                events_service.process_manual_entry(
                    no_card_student,
                    notes="Забув картку",
                    event_time=now - timedelta(hours=1, minutes=45),
                )

            # An unregistered card scan, to populate the "problematic events" report.
            events_service.process_scan_event(
                "DEADBEEF00", reader.code, event_time=now - timedelta(minutes=30)
            )

        self.stdout.write(self.style.SUCCESS("Demo data seeded."))
        self.stdout.write(
            "Check: /  /students/  /classes/  /cards/  /guard/  /reports/meal/  /admin/"
        )
