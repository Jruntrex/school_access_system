"""Import students from a CSV file (spec section 6.1).

Expected columns (header row required): last_name, first_name, class_name,
meal_option_code. meal_option_code defaults to STANDARD when blank/unknown.

Usage:
    python manage.py import_students students.csv --academic-year "2026/2027"
"""

from django.core.management.base import BaseCommand, CommandError

from school_access.models import AcademicYear
from school_access.services.imports import import_students, parse_csv_rows


class Command(BaseCommand):
    help = "Import students (last_name, first_name, class_name, meal_option_code) from a CSV file"

    def add_arguments(self, parser):
        parser.add_argument("csv_path", help="Path to the CSV file")
        parser.add_argument(
            "--academic-year",
            required=True,
            help="Name of an existing academic year, e.g. 2026/2027",
        )
        parser.add_argument("--delimiter", default=",")

    def handle(self, *args, **options):
        try:
            academic_year = AcademicYear.objects.get(name=options["academic_year"])
        except AcademicYear.DoesNotExist as exc:
            raise CommandError(
                f"Academic year {options['academic_year']!r} does not exist"
            ) from exc

        with open(options["csv_path"], "rb") as f:
            rows = parse_csv_rows(f, delimiter=options["delimiter"])

        result = import_students(rows, academic_year)

        self.stdout.write(self.style.SUCCESS(f"Created {result.created_students} students"))
        for error in result.errors:
            self.stdout.write(self.style.WARNING(error))
