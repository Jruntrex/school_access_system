"""Read-side report queries (spec section 8). Pattern borrowed from
Mentorly's main/selectors.py: keep report logic out of views, as plain
querysets the caller can render, export as CSV, or serialize as JSON.
"""

from datetime import date

from django.db.models import QuerySet

from school_access.models import AccessEvent, AttendanceDaily, MealOption, Student

_ORDER_BY_CLASS_THEN_NAME = (
    "school_class__grade",
    "school_class__letter",
    "student__last_name",
    "student__first_name",
)


def daily_meal_report(attendance_date: date) -> QuerySet:
    """8.1 — present students who should be included in meal prep (excludes NO_MEAL)."""
    return (
        AttendanceDaily.objects.filter(
            attendance_date=attendance_date,
            student__meal_assignments__status="ACTIVE",
        )
        .exclude(
            student__meal_assignments__status="ACTIVE",
            student__meal_assignments__meal_option__code=MealOption.NO_MEAL,
        )
        .select_related("student", "school_class", "student__meal_assignments__meal_option")
        .values(
            "school_class__name",
            "school_class__grade",
            "school_class__letter",
            "student__last_name",
            "student__first_name",
            "first_entry_time",
            "student__meal_assignments__meal_option__code",
            "student__meal_assignments__meal_option__name",
        )
        .order_by(*_ORDER_BY_CLASS_THEN_NAME)
    )


def present_students(attendance_date: date) -> QuerySet:
    """8.2 — all present students, regardless of meal option."""
    return (
        AttendanceDaily.objects.filter(attendance_date=attendance_date)
        .select_related("student", "school_class")
        .values(
            "school_class__name",
            "school_class__grade",
            "school_class__letter",
            "student__last_name",
            "student__first_name",
            "first_entry_time",
        )
        .order_by(*_ORDER_BY_CLASS_THEN_NAME)
    )


def present_students_with_meal_option(attendance_date: date, meal_option_code: str) -> QuerySet:
    """8.3 — present students filtered to one meal option (e.g. SPECIAL)."""
    return (
        AttendanceDaily.objects.filter(
            attendance_date=attendance_date,
            student__meal_assignments__status="ACTIVE",
            student__meal_assignments__meal_option__code=meal_option_code,
        )
        .select_related("student", "school_class")
        .values(
            "school_class__name",
            "student__last_name",
            "student__first_name",
            "first_entry_time",
        )
        .order_by(*_ORDER_BY_CLASS_THEN_NAME)
    )


def problematic_card_events() -> QuerySet:
    """8.4 — unknown/inactive/unassigned card scans, for troubleshooting."""
    return (
        AccessEvent.objects.filter(
            event_status__in=[
                AccessEvent.EventStatus.UNKNOWN_CARD,
                AccessEvent.EventStatus.INACTIVE_CARD,
                AccessEvent.EventStatus.NO_ACTIVE_ASSIGNMENT,
            ]
        )
        .select_related("reader")
        .values(
            "event_time",
            "event_status",
            "reader__code",
            "reader__name",
            "scanned_card_uid_hash",
        )
        .order_by("-event_time")
    )


def students_without_active_card() -> QuerySet:
    """8.5 — active students with no active RFID card assignment."""
    return (
        Student.objects.filter(status=Student.Status.ACTIVE)
        .filter(class_enrollments__status="ACTIVE")
        .exclude(card_assignments__status="ACTIVE")
        .select_related()
        .values(
            "class_enrollments__school_class__name",
            "class_enrollments__school_class__grade",
            "class_enrollments__school_class__letter",
            "last_name",
            "first_name",
        )
        .order_by(
            "class_enrollments__school_class__grade",
            "class_enrollments__school_class__letter",
            "last_name",
            "first_name",
        )
    )


def absent_students(attendance_date: date) -> QuerySet:
    """8.6 — active, enrolled students with no attendance_daily row for the date."""
    return (
        Student.objects.filter(status=Student.Status.ACTIVE)
        .filter(class_enrollments__status="ACTIVE")
        .exclude(attendance_records__attendance_date=attendance_date)
        .values(
            "class_enrollments__school_class__name",
            "class_enrollments__school_class__grade",
            "class_enrollments__school_class__letter",
            "last_name",
            "first_name",
        )
        .order_by(
            "class_enrollments__school_class__grade",
            "class_enrollments__school_class__letter",
            "last_name",
            "first_name",
        )
    )
