"""Student/class import (spec sections 6.1, 6.2)."""

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date
from typing import IO

from django.db import transaction

from school_access.models import (
    AcademicYear,
    MealOption,
    SchoolClass,
    Student,
    StudentClassEnrollment,
    StudentMealAssignment,
)

CLASS_NAME_RE = re.compile(r"^\s*(\d{1,2})\s*-\s*(\S+)\s*$")


class ClassNameParseError(ValueError):
    pass


def parse_class_name(class_name: str) -> tuple[int, str]:
    """"5-А" -> (5, "А"). Raises ClassNameParseError on malformed input."""
    match = CLASS_NAME_RE.match(class_name)
    if not match:
        raise ClassNameParseError(f"Cannot parse class name: {class_name!r}")
    grade, letter = match.groups()
    return int(grade), letter


@dataclass
class ImportRow:
    last_name: str
    first_name: str
    class_name: str
    meal_option_code: str = ""


@dataclass
class ImportResult:
    created_students: int = 0
    errors: list[str] = field(default_factory=list)


def parse_csv_rows(fileobj: IO[bytes], delimiter: str = ",") -> list[ImportRow]:
    """Reads last_name,first_name,class_name,meal_option_code from a
    file-like object opened in binary mode (CLI file handle or an uploaded
    file from a web form) — shared by the management command and the web
    import view."""
    text = io.TextIOWrapper(fileobj, encoding="utf-8")
    reader = csv.DictReader(text, delimiter=delimiter)
    return [
        ImportRow(
            last_name=row["last_name"],
            first_name=row["first_name"],
            class_name=row["class_name"],
            meal_option_code=row.get("meal_option_code", ""),
        )
        for row in reader
    ]


def _get_or_create_class(academic_year: AcademicYear, class_name: str) -> SchoolClass:
    grade, letter = parse_class_name(class_name)
    school_class, _ = SchoolClass.objects.get_or_create(
        academic_year=academic_year,
        grade=grade,
        letter=letter,
        defaults={"name": class_name},
    )
    return school_class


def _resolve_meal_option(code: str) -> MealOption:
    code = (code or "").strip().upper() or MealOption.STANDARD
    meal_option = MealOption.objects.filter(code=code).first()
    if meal_option is None:
        meal_option = MealOption.objects.get(code=MealOption.STANDARD)
    return meal_option


@transaction.atomic
def import_students(rows: list[ImportRow], academic_year: AcademicYear) -> ImportResult:
    result = ImportResult()
    today = date.today()

    for i, row in enumerate(rows, start=1):
        try:
            school_class = _get_or_create_class(academic_year, row.class_name)
        except ClassNameParseError as exc:
            result.errors.append(f"Row {i}: {exc}")
            continue

        meal_option = _resolve_meal_option(row.meal_option_code)

        student = Student.objects.create(
            last_name=row.last_name.strip(),
            first_name=row.first_name.strip(),
            status=Student.Status.ACTIVE,
        )
        StudentClassEnrollment.objects.create(
            student=student,
            school_class=school_class,
            valid_from=today,
            status="ACTIVE",
        )
        StudentMealAssignment.objects.create(
            student=student,
            meal_option=meal_option,
            valid_from=today,
            status="ACTIVE",
        )
        result.created_students += 1

    return result
