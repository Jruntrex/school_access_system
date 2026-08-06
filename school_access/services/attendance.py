"""Daily attendance derivation from access events (spec section 6.6)."""

import logging

from django.db import IntegrityError, transaction

from school_access.models import AttendanceDaily, StudentClassEnrollment

logger = logging.getLogger(__name__)


def ensure_attendance_daily(event) -> AttendanceDaily | None:
    """Create the attendance_daily row for a VALID ENTER_SCHOOL event, if one
    does not already exist for (attendance_date, student). Never creates a
    second row for the same day — later ENTER_SCHOOL events on the same day
    are recorded in access_events only. A re-entry after an earlier exit
    bumps last_entry_time and clears last_exit_time, since the student is
    inside again; first_entry_time never changes after creation.
    """
    student = event.student
    if student is None:
        return None

    attendance_date = event.event_time.date()

    with transaction.atomic():
        existing = AttendanceDaily.objects.filter(
            attendance_date=attendance_date, student=student
        ).first()
        if existing is not None:
            existing.last_entry_time = event.event_time
            existing.last_entry_event = event
            existing.last_exit_time = None
            existing.last_exit_event = None
            existing.save(
                update_fields=[
                    "last_entry_time",
                    "last_entry_event",
                    "last_exit_time",
                    "last_exit_event",
                    "updated_at",
                ]
            )
            return existing

        enrollment = (
            StudentClassEnrollment.objects.select_related("school_class")
            .filter(student=student, status="ACTIVE")
            .first()
        )
        if enrollment is None:
            logger.warning(
                "No active class enrollment for student %s — skipping attendance_daily",
                student.pk,
            )
            return None

        try:
            return AttendanceDaily.objects.create(
                attendance_date=attendance_date,
                student=student,
                school_class=enrollment.school_class,
                first_entry_time=event.event_time,
                first_entry_event=event,
                last_entry_time=event.event_time,
                last_entry_event=event,
            )
        except IntegrityError:
            # Lost a race with another concurrent valid entry for the same
            # student/day — the unique_attendance_per_day constraint wins.
            return AttendanceDaily.objects.get(
                attendance_date=attendance_date, student=student
            )


def record_exit(event) -> AttendanceDaily | None:
    """Stamps the attendance_daily row for a VALID EXIT_SCHOOL event with the
    exit time, so the class report can show "у школі" vs "вийшов". A no-op
    if there is no attendance_daily row yet for the day (exit without a
    prior recorded entry shouldn't normally happen).
    """
    student = event.student
    if student is None:
        return None

    attendance_date = event.event_time.date()

    with transaction.atomic():
        row = AttendanceDaily.objects.filter(
            attendance_date=attendance_date, student=student
        ).first()
        if row is None:
            logger.warning(
                "Exit scan with no attendance_daily row for student %s on %s — skipping",
                student.pk,
                attendance_date,
            )
            return None

        row.last_exit_time = event.event_time
        row.last_exit_event = event
        row.save(update_fields=["last_exit_time", "last_exit_event", "updated_at"])
        return row
