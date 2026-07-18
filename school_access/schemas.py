from ninja import Schema


class ScanRequest(Schema):
    uid: str
    reader_code: str


class ScanResponse(Schema):
    mode: str  # "assign" | "attendance" | "duplicate"
    event_status: str | None = None
    student: str | None = None
    uid: str | None = None


class ManualEntryRequest(Schema):
    student_id: int
    notes: str = ""


class AssignModeRequest(Schema):
    action: str  # "start" | "stop"


class ConfirmAssignmentRequest(Schema):
    student_id: int


class EndAssignmentRequest(Schema):
    student_id: int
    reason: str = "OTHER"


class ScanStateOut(Schema):
    active: bool
    uid: str | None = None
    scanned_at: str | None = None
    started_at: str | None = None


class OkResponse(Schema):
    ok: bool
