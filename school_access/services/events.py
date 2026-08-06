"""Scan/manual access event ingestion (spec section 6.5 and "Manual Guard
Entry"). Duplicate-scan filtering, card/assignment resolution and
event_status determination live here — access_events itself stores only
the resulting facts.
"""

from datetime import timedelta

from django.utils import timezone

from school_access.models import (
    AccessEvent,
    RfidCard,
    RfidCardAssignment,
    RfidReader,
    Student,
)
from school_access.services import attendance as attendance_service
from school_access.services.hashing import compute_card_uid_hash, normalize_uid

DUPLICATE_WINDOW_SECONDS = 3


def _is_duplicate(scanned_card_uid_hash: str, reader: RfidReader | None, event_time) -> bool:
    """Same card + same reader within a few seconds is a single physical tap
    read more than once (the reader loop re-detects a card still sitting in
    the field), not a real second scan. Kept short deliberately: with the
    entry/exit toggle, a genuine second tap seconds later must go through —
    a long window here would silently eat legitimate exit scans.
    """
    window_start = event_time - timedelta(seconds=DUPLICATE_WINDOW_SECONDS)
    return AccessEvent.objects.filter(
        scanned_card_uid_hash=scanned_card_uid_hash,
        reader=reader,
        event_time__gte=window_start,
        event_time__lte=event_time,
    ).exists()


def _next_direction(student: Student, event_time) -> str:
    """Single vestibule reader toggles: first scan of the day is an entry,
    the next one an exit, and so on — mirrors a physical turnstile rather
    than needing a dedicated exit reader.
    """
    attendance_date = event_time.date()
    last = (
        AccessEvent.objects.filter(
            student=student,
            event_status=AccessEvent.EventStatus.VALID,
            event_type__in=[
                AccessEvent.EventType.ENTER_SCHOOL,
                AccessEvent.EventType.EXIT_SCHOOL,
            ],
            event_time__date=attendance_date,
        )
        .order_by("-event_time")
        .first()
    )
    if last is None or last.event_type == AccessEvent.EventType.EXIT_SCHOOL:
        return AccessEvent.EventType.ENTER_SCHOOL
    return AccessEvent.EventType.EXIT_SCHOOL


def process_scan_event(raw_uid: str, reader_code: str, event_time=None) -> AccessEvent | None:
    """Processes one ESP32 scan. Returns the created AccessEvent, or None if
    the scan was a duplicate and was dropped per the spec's dedup rule.
    """
    event_time = event_time or timezone.now()

    uid = normalize_uid(raw_uid)
    scanned_hash = compute_card_uid_hash(uid)

    reader = RfidReader.objects.filter(code=reader_code, status="ACTIVE").first()

    if _is_duplicate(scanned_hash, reader, event_time):
        return None

    card = RfidCard.objects.filter(card_uid_hash=scanned_hash).first()
    assignment = None
    student = None

    if card is None:
        event_status = AccessEvent.EventStatus.UNKNOWN_CARD
    elif card.status != RfidCard.Status.ACTIVE:
        event_status = AccessEvent.EventStatus.INACTIVE_CARD
    else:
        assignment = RfidCardAssignment.objects.filter(
            card=card, status="ACTIVE"
        ).select_related("student").first()
        if assignment is None:
            event_status = AccessEvent.EventStatus.NO_ACTIVE_ASSIGNMENT
        else:
            event_status = AccessEvent.EventStatus.VALID
            student = assignment.student

    if reader and reader.purpose == RfidReader.Purpose.MEAL_TAKEN:
        event_type = RfidReader.Purpose.MEAL_TAKEN
    elif event_status == AccessEvent.EventStatus.VALID:
        # Single vestibule reader toggling entry/exit per scan — an
        # unregistered reader code still gets recorded (reader=None) so it
        # shows up for troubleshooting.
        event_type = _next_direction(student, event_time)
    else:
        # Unknown/inactive/unassigned card: no student to toggle a direction
        # for, default to entry so it still surfaces in the entry log.
        event_type = AccessEvent.EventType.ENTER_SCHOOL

    event = AccessEvent.objects.create(
        event_time=event_time,
        event_type=event_type,
        event_source=AccessEvent.EventSource.RFID_READER,
        event_status=event_status,
        reader=reader,
        scanned_card_uid_hash=scanned_hash,
        card=card,
        card_assignment=assignment,
        student=student,
    )

    if event_status == AccessEvent.EventStatus.VALID:
        if event_type == AccessEvent.EventType.ENTER_SCHOOL:
            attendance_service.ensure_attendance_daily(event)
        elif event_type == AccessEvent.EventType.EXIT_SCHOOL:
            attendance_service.record_exit(event)

    return event


def process_manual_entry(student: Student, notes: str = "", event_time=None) -> AccessEvent:
    """Guard-registered entry for a student without a working card (spec
    "Manual Guard Entry"). Caller is responsible for authorizing the guard.
    """
    event_time = event_time or timezone.now()

    event = AccessEvent.objects.create(
        event_time=event_time,
        event_type=AccessEvent.EventType.ENTER_SCHOOL,
        event_source=AccessEvent.EventSource.MANUAL_BY_GUARD,
        event_status=AccessEvent.EventStatus.VALID,
        student=student,
        notes=notes,
    )
    attendance_service.ensure_attendance_daily(event)
    return event


def process_manual_exit(student: Student, notes: str = "", event_time=None) -> AccessEvent:
    """Guard-registered exit — the counterpart to process_manual_entry, for
    correcting a card that failed on the way out, or a guard who watched a
    student leave without scanning.
    """
    event_time = event_time or timezone.now()

    event = AccessEvent.objects.create(
        event_time=event_time,
        event_type=AccessEvent.EventType.EXIT_SCHOOL,
        event_source=AccessEvent.EventSource.MANUAL_BY_GUARD,
        event_status=AccessEvent.EventStatus.VALID,
        student=student,
        notes=notes,
    )
    attendance_service.record_exit(event)
    return event
