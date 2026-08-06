"""Django Ninja routers.

/access is deliberately unauthenticated at the Ninja layer — the ESP32
reader authenticates via the HMAC signature (X-Timestamp/X-Signature),
not a Django session, matching the firmware in firmware/rfid-moodle.ino.
/cards and /reports require a staff Django session.
"""

from datetime import date as date_cls

from django.shortcuts import get_object_or_404
from ninja import Router
from ninja.errors import HttpError
from ninja.security import django_auth

from school_access import selectors
from school_access.models import AccessEvent, Student
from school_access.schemas import (
    AssignModeRequest,
    ConfirmAssignmentRequest,
    EndAssignmentRequest,
    ManualEntryRequest,
    OkResponse,
    ScanRequest,
    ScanResponse,
    ScanStateOut,
)
from school_access.services import card_assignment
from school_access.services import events as events_service
from school_access.services.hashing import verify_device_signature

access_router = Router(tags=["access"])
cards_router = Router(tags=["cards"], auth=django_auth)
reports_router = Router(tags=["reports"], auth=django_auth)


def _require_staff(request):
    if not request.auth.is_staff:
        raise HttpError(403, "Staff only")


@access_router.post("/scan/", response=ScanResponse)
def scan(request, payload: ScanRequest):
    timestamp = request.headers.get("X-Timestamp", "")
    signature = request.headers.get("X-Signature", "")
    if not verify_device_signature(payload.uid, timestamp, signature):
        raise HttpError(403, "Invalid signature")

    state = card_assignment.read_assign_state()
    if state.get("active"):
        card_assignment.buffer_scanned_uid(payload.uid)
        return ScanResponse(mode="assign", uid=payload.uid.strip().upper())

    event = events_service.process_scan_event(payload.uid, payload.reader_code)
    if event is None:
        return ScanResponse(mode="duplicate")
    direction = None
    if event.event_status == AccessEvent.EventStatus.VALID:
        if event.event_type == AccessEvent.EventType.ENTER_SCHOOL:
            direction = "ENTRY"
        elif event.event_type == AccessEvent.EventType.EXIT_SCHOOL:
            direction = "EXIT"
    return ScanResponse(
        mode="attendance",
        event_status=event.event_status,
        student=str(event.student) if event.student else None,
        direction=direction,
    )


@access_router.post("/manual/", auth=django_auth, response=OkResponse)
def manual_entry(request, payload: ManualEntryRequest):
    _require_staff(request)
    student = get_object_or_404(Student, pk=payload.student_id)
    events_service.process_manual_entry(student, notes=payload.notes)
    return {"ok": True}


@access_router.post("/manual-exit/", auth=django_auth, response=OkResponse)
def manual_exit(request, payload: ManualEntryRequest):
    _require_staff(request)
    student = get_object_or_404(Student, pk=payload.student_id)
    events_service.process_manual_exit(student, notes=payload.notes)
    return {"ok": True}


@cards_router.get("/scan-state/", response=ScanStateOut)
def scan_state(request):
    return card_assignment.read_assign_state()


@cards_router.post("/assign-mode/", response=OkResponse)
def assign_mode(request, payload: AssignModeRequest):
    _require_staff(request)
    if payload.action == "start":
        card_assignment.start_assign_mode()
    else:
        card_assignment.stop_assign_mode()
    return {"ok": True}


@cards_router.post("/confirm-assignment/", response=OkResponse)
def confirm_assignment(request, payload: ConfirmAssignmentRequest):
    _require_staff(request)
    state = card_assignment.read_assign_state()
    uid = state.get("uid")
    if not uid:
        raise HttpError(400, "No card scanned yet")
    student = get_object_or_404(Student, pk=payload.student_id)
    try:
        card_assignment.assign_card(uid, student)
    except ValueError as exc:
        raise HttpError(409, str(exc))
    return {"ok": True}


@cards_router.post("/end-assignment/", response=OkResponse)
def end_assignment(request, payload: EndAssignmentRequest):
    _require_staff(request)
    student = get_object_or_404(Student, pk=payload.student_id)
    card_assignment.end_card_assignment(student, reason=payload.reason)
    return {"ok": True}


@reports_router.get("/meal/")
def meal_report(request, report_date: date_cls = None):
    report_date = report_date or date_cls.today()
    return {"date": str(report_date), "rows": list(selectors.daily_meal_report(report_date))}


@reports_router.get("/present/")
def present_report(request, report_date: date_cls = None):
    report_date = report_date or date_cls.today()
    return {"date": str(report_date), "rows": list(selectors.present_students(report_date))}


@reports_router.get("/absent/")
def absent_report(request, report_date: date_cls = None):
    report_date = report_date or date_cls.today()
    return {"date": str(report_date), "rows": list(selectors.absent_students(report_date))}


@reports_router.get("/attendance-by-class/")
def attendance_by_class_report(request, report_date: date_cls = None):
    """Backs the live-updating /reports/attendance/ page (poll-based refresh,
    no full page reload)."""
    report_date = report_date or date_cls.today()
    class_rows = selectors.attendance_by_class(report_date)
    return {
        "date": str(report_date),
        "class_rows": class_rows,
        "total_present": sum(row["present_count"] for row in class_rows),
        "total_absent": sum(row["absent_count"] for row in class_rows),
    }


@reports_router.get("/problematic-events/")
def problematic_events_report(request):
    return {"rows": list(selectors.problematic_card_events())}
