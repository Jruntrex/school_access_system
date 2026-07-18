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
from school_access.services.attendance import ensure_attendance_daily
from school_access.services.hashing import compute_card_uid_hash, normalize_uid

DUPLICATE_WINDOW_SECONDS = 30


def _is_duplicate(scanned_card_uid_hash: str, reader: RfidReader | None, event_time) -> bool:
    """Same card + same reader within 30s is not stored (spec: Duplicate Rule)."""
    window_start = event_time - timedelta(seconds=DUPLICATE_WINDOW_SECONDS)
    return AccessEvent.objects.filter(
        scanned_card_uid_hash=scanned_card_uid_hash,
        reader=reader,
        event_time__gte=window_start,
        event_time__lte=event_time,
    ).exists()


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

    # MVP only has vestibule/ENTER_SCHOOL readers; an unregistered reader
    # code still gets recorded (reader=None) so it shows up for troubleshooting.
    event_type = reader.purpose if reader else AccessEvent.EventType.ENTER_SCHOOL

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

    if event_status == AccessEvent.EventStatus.VALID and event_type == AccessEvent.EventType.ENTER_SCHOOL:
        ensure_attendance_daily(event)

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
    ensure_attendance_daily(event)
    return event
