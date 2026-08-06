"""RFID card issuance/replacement (spec sections 6.3, 6.4, 10.3).

The "scan a card, then confirm who it belongs to" workflow is ported from
Mentorly's file-based scan-buffer (`_rfid_read_state`/`_rfid_write_state` in
main/views.py): while assign-mode is active, the next scan from a reader is
held in this transient buffer instead of being written to access_events, so
an admin can confirm the assignment through the UI. The buffer only ever
holds the normalized UID briefly and is cleared on confirm/timeout — it is
never persisted to the database (see spec section 3.3).
"""

import json
from datetime import date, datetime
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from school_access.models import RfidCard, RfidCardAssignment, Student
from school_access.services.hashing import compute_card_uid_hash, normalize_uid

ASSIGN_STATE_FILE: Path = settings.BASE_DIR / ".rfid_assign_state.json"
ASSIGN_MODE_TIMEOUT_SECONDS = 300


def read_assign_state() -> dict:
    try:
        state = json.loads(ASSIGN_STATE_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {"active": False, "uid": None, "scanned_at": None, "started_at": None}

    if state.get("active") and state.get("started_at"):
        started = datetime.fromisoformat(state["started_at"])
        if (datetime.now() - started).total_seconds() > ASSIGN_MODE_TIMEOUT_SECONDS:
            return _reset_state()
    return state


def _write_state(state: dict) -> None:
    try:
        ASSIGN_STATE_FILE.write_text(json.dumps(state), encoding="utf-8")
    except OSError:
        pass


def _reset_state() -> dict:
    state = {"active": False, "uid": None, "scanned_at": None, "started_at": None}
    _write_state(state)
    return state


def start_assign_mode() -> None:
    _write_state(
        {
            "active": True,
            "uid": None,
            "scanned_at": None,
            "started_at": datetime.now().isoformat(),
        }
    )


def stop_assign_mode() -> None:
    _reset_state()


def buffer_scanned_uid(raw_uid: str) -> None:
    """Called from the scan endpoint when assign-mode is active, instead of
    routing the scan through normal access-event processing."""
    state = read_assign_state()
    state["uid"] = normalize_uid(raw_uid)
    state["scanned_at"] = datetime.now().isoformat()
    _write_state(state)


@transaction.atomic
def assign_card(raw_uid: str, student: Student) -> RfidCardAssignment:
    """Assigns a (possibly new) card to a student. Ends any previous active
    assignment for that student, and refuses to hand out a card that is
    already actively assigned to someone else.
    """
    uid = normalize_uid(raw_uid)
    card_uid_hash = compute_card_uid_hash(uid)

    card, _ = RfidCard.objects.select_for_update().get_or_create(
        card_uid_hash=card_uid_hash, defaults={"status": RfidCard.Status.ACTIVE}
    )
    if card.status != RfidCard.Status.ACTIVE:
        # Re-issuing a card that was previously marked lost/damaged/retired —
        # handing it back out means it's back in service.
        card.status = RfidCard.Status.ACTIVE
        card.deactivated_at = None
        card.deactivation_reason = None
        card.save(update_fields=["status", "deactivated_at", "deactivation_reason"])

    existing_for_card = (
        RfidCardAssignment.objects.select_for_update()
        .filter(card=card, status="ACTIVE")
        .exclude(student=student)
        .first()
    )
    if existing_for_card is not None:
        raise ValueError(
            f"Card is already assigned to student #{existing_for_card.student_id}"
        )

    today = date.today()

    current = (
        RfidCardAssignment.objects.select_for_update()
        .filter(student=student, status="ACTIVE")
        .first()
    )
    if current is not None:
        if current.card_id == card.id:
            stop_assign_mode()
            return current
        current.status = "ENDED"
        current.assigned_to = today
        current.end_reason = RfidCardAssignment.EndReason.REPLACED
        current.save(update_fields=["status", "assigned_to", "end_reason"])

    assignment = RfidCardAssignment.objects.create(
        card=card, student=student, assigned_from=today, status="ACTIVE"
    )
    stop_assign_mode()
    return assignment


@transaction.atomic
def end_card_assignment(
    student: Student, reason: str = RfidCardAssignment.EndReason.OTHER
) -> None:
    """Ends a student's active card assignment (spec section 6.4/10.3).
    `reason` LOST/DAMAGED also deactivates the underlying card so it cannot
    be reused."""
    assignment = (
        RfidCardAssignment.objects.select_for_update()
        .filter(student=student, status="ACTIVE")
        .select_related("card")
        .first()
    )
    if assignment is None:
        return

    assignment.status = "ENDED"
    assignment.assigned_to = date.today()
    assignment.end_reason = reason
    assignment.save(update_fields=["status", "assigned_to", "end_reason"])

    if reason in (RfidCardAssignment.EndReason.LOST, RfidCardAssignment.EndReason.DAMAGED):
        card = assignment.card
        card.status = reason
        card.deactivated_at = timezone.now()
        card.deactivation_reason = reason
        card.save(update_fields=["status", "deactivated_at", "deactivation_reason"])
