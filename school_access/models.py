from django.db import models
from django.db.models import Q, UniqueConstraint

# ==========================================
# Shared status vocabularies (see school_access_schema.sql)
# ==========================================


class ActiveEndedStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    ENDED = "ENDED", "Ended"


class EndReason(models.TextChoices):
    """Shared by rfid_cards.deactivation_reason and
    rfid_card_assignments.end_reason."""

    LOST = "LOST", "Lost"
    DAMAGED = "DAMAGED", "Damaged"
    REPLACED = "REPLACED", "Replaced"
    STUDENT_LEFT = "STUDENT_LEFT", "Student left"
    OTHER = "OTHER", "Other"


def schema_table(name: str) -> str:
    """Pre-quoted "school_access"."name" — Django's postgres quote_name()
    passes an already-quoted identifier through unchanged, so this is how
    a real dedicated schema (rather than the default "public") is achieved
    without a second database connection/router.
    """
    return f'"school_access"."{name}"'


# ==========================================
# 1. academic_years
# ==========================================


class AcademicYear(models.Model):
    name = models.CharField(max_length=20, unique=True)
    starts_on = models.DateField()
    ends_on = models.DateField()
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = schema_table("academic_years")
        constraints = [
            models.CheckConstraint(
                condition=Q(starts_on__lt=models.F("ends_on")),
                name="chk_academic_years_dates",
            ),
        ]
        ordering = ["-starts_on"]

    def __str__(self) -> str:
        return self.name


# ==========================================
# 2. classes
# ==========================================


class SchoolClass(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"

    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.PROTECT, related_name="classes"
    )
    grade = models.PositiveSmallIntegerField()
    letter = models.CharField(max_length=5)
    name = models.CharField(max_length=20)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = schema_table("classes")
        constraints = [
            UniqueConstraint(
                fields=["academic_year", "grade", "letter"],
                name="uq_classes_year_grade_letter",
            ),
            models.CheckConstraint(
                condition=Q(grade__gte=1) & Q(grade__lte=12),
                name="chk_classes_grade",
            ),
        ]
        indexes = [
            models.Index(fields=["academic_year"], name="idx_classes_academic_year_id"),
        ]
        ordering = ["grade", "letter"]

    def __str__(self) -> str:
        return self.name


# ==========================================
# 3. students
# ==========================================


class Student(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"
        LEFT_SCHOOL = "LEFT_SCHOOL", "Left school"

    last_name = models.CharField(max_length=100)
    first_name = models.CharField(max_length=100)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = schema_table("students")
        indexes = [
            models.Index(fields=["last_name", "first_name"], name="idx_students_name"),
        ]
        ordering = ["last_name", "first_name"]

    def __str__(self) -> str:
        return f"{self.last_name} {self.first_name}"


# ==========================================
# 4. student_class_enrollments
# ==========================================


class StudentClassEnrollment(models.Model):
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="class_enrollments"
    )
    school_class = models.ForeignKey(
        SchoolClass,
        on_delete=models.PROTECT,
        related_name="enrollments",
        db_column="class_id",
    )
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=ActiveEndedStatus.choices,
        default=ActiveEndedStatus.ACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = schema_table("student_class_enrollments")
        constraints = [
            UniqueConstraint(
                fields=["student"],
                condition=Q(status="ACTIVE"),
                name="uq_student_active_class_enrollment",
            ),
            models.CheckConstraint(
                condition=Q(valid_to__isnull=True) | Q(valid_to__gte=models.F("valid_from")),
                name="chk_student_class_enrollments_dates",
            ),
        ]
        indexes = [
            models.Index(fields=["student"], name="idx_sce_student_id"),
            models.Index(fields=["school_class"], name="idx_sce_class_id"),
        ]
        ordering = ["-valid_from"]

    def __str__(self) -> str:
        return f"{self.student} -> {self.school_class} ({self.status})"


# ==========================================
# 5. meal_options
# ==========================================


class MealOption(models.Model):
    STANDARD = "STANDARD"
    NO_MEAL = "NO_MEAL"
    SPECIAL = "SPECIAL"

    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = schema_table("meal_options")
        ordering = ["code"]

    def __str__(self) -> str:
        return self.name


# ==========================================
# 6. student_meal_assignments
# ==========================================


class StudentMealAssignment(models.Model):
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="meal_assignments"
    )
    meal_option = models.ForeignKey(
        MealOption, on_delete=models.PROTECT, related_name="assignments"
    )
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=ActiveEndedStatus.choices,
        default=ActiveEndedStatus.ACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = schema_table("student_meal_assignments")
        constraints = [
            UniqueConstraint(
                fields=["student"],
                condition=Q(status="ACTIVE"),
                name="uq_student_active_meal_assignment",
            ),
            models.CheckConstraint(
                condition=Q(valid_to__isnull=True) | Q(valid_to__gte=models.F("valid_from")),
                name="chk_student_meal_assignments_dates",
            ),
        ]
        indexes = [
            models.Index(fields=["student"], name="idx_sma_student_id"),
            models.Index(fields=["meal_option"], name="idx_sma_meal_id"),
        ]
        ordering = ["-valid_from"]

    def __str__(self) -> str:
        return f"{self.student} -> {self.meal_option} ({self.status})"


# ==========================================
# 7. rfid_cards
# ==========================================


class RfidCard(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        LOST = "LOST", "Lost"
        DAMAGED = "DAMAGED", "Damaged"
        RETIRED = "RETIRED", "Retired"

    card_uid_hash = models.CharField(max_length=128, unique=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    created_at = models.DateTimeField(auto_now_add=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)
    deactivation_reason = models.CharField(
        max_length=30, choices=EndReason.choices, null=True, blank=True
    )

    class Meta:
        db_table = schema_table("rfid_cards")
        indexes = [
            models.Index(fields=["status"], name="idx_rfid_cards_status"),
        ]
        ordering = ["-id"]

    def __str__(self) -> str:
        return f"Card #{self.pk} ({self.status})"


# ==========================================
# 8. rfid_card_assignments
# ==========================================


class RfidCardAssignment(models.Model):
    EndReason = EndReason

    card = models.ForeignKey(
        RfidCard, on_delete=models.CASCADE, related_name="assignments"
    )
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="card_assignments"
    )
    assigned_from = models.DateField()
    assigned_to = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=ActiveEndedStatus.choices,
        default=ActiveEndedStatus.ACTIVE,
    )
    end_reason = models.CharField(
        max_length=30, choices=EndReason.choices, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = schema_table("rfid_card_assignments")
        constraints = [
            UniqueConstraint(
                fields=["card"],
                condition=Q(status="ACTIVE"),
                name="uq_active_assignment_per_card",
            ),
            UniqueConstraint(
                fields=["student"],
                condition=Q(status="ACTIVE"),
                name="uq_active_assignment_per_student",
            ),
            models.CheckConstraint(
                condition=Q(assigned_to__isnull=True) | Q(assigned_to__gte=models.F("assigned_from")),
                name="chk_rfid_card_assignments_dates",
            ),
        ]
        indexes = [
            models.Index(fields=["card"], name="idx_rca_card_id"),
            models.Index(fields=["student"], name="idx_rca_student_id"),
        ]
        ordering = ["-assigned_from"]

    def __str__(self) -> str:
        return f"{self.card} -> {self.student} ({self.status})"


# ==========================================
# 9. reader_locations
# ==========================================


class ReaderLocation(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = schema_table("reader_locations")
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


# ==========================================
# 10. rfid_readers
# ==========================================


class RfidReader(models.Model):
    class Purpose(models.TextChoices):
        ENTER_SCHOOL = "ENTER_SCHOOL", "Enter school"
        EXIT_SCHOOL = "EXIT_SCHOOL", "Exit school"
        MEAL_TAKEN = "MEAL_TAKEN", "Meal taken"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"

    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    location = models.ForeignKey(
        ReaderLocation, on_delete=models.PROTECT, related_name="readers"
    )
    purpose = models.CharField(max_length=30, choices=Purpose.choices)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = schema_table("rfid_readers")
        indexes = [
            models.Index(fields=["location"], name="idx_rfid_readers_location_id"),
            models.Index(fields=["purpose"], name="idx_rfid_readers_purpose"),
        ]
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} ({self.get_purpose_display()})"


# ==========================================
# 11. access_events
# ==========================================


class AccessEvent(models.Model):
    class EventType(models.TextChoices):
        ENTER_SCHOOL = "ENTER_SCHOOL", "Enter school"
        EXIT_SCHOOL = "EXIT_SCHOOL", "Exit school"
        MEAL_TAKEN = "MEAL_TAKEN", "Meal taken"

    class EventSource(models.TextChoices):
        RFID_READER = "RFID_READER", "RFID reader"
        MANUAL_BY_GUARD = "MANUAL_BY_GUARD", "Manual (guard)"

    class EventStatus(models.TextChoices):
        VALID = "VALID", "Valid"
        UNKNOWN_CARD = "UNKNOWN_CARD", "Unknown card"
        INACTIVE_CARD = "INACTIVE_CARD", "Inactive card"
        NO_ACTIVE_ASSIGNMENT = "NO_ACTIVE_ASSIGNMENT", "No active assignment"

    event_time = models.DateTimeField()
    event_type = models.CharField(max_length=30, choices=EventType.choices)
    event_source = models.CharField(max_length=30, choices=EventSource.choices)
    event_status = models.CharField(max_length=30, choices=EventStatus.choices)

    # PROTECT, not SET_NULL: chk_access_events_rfid_fields requires reader_id
    # to stay set for RFID_READER-sourced rows, so nulling it out on delete
    # would violate the constraint. Readers are deactivated, not deleted.
    reader = models.ForeignKey(
        RfidReader,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="events",
    )
    scanned_card_uid_hash = models.CharField(max_length=128, null=True, blank=True)
    card = models.ForeignKey(
        RfidCard,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )
    card_assignment = models.ForeignKey(
        RfidCardAssignment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )
    # PROTECT, not SET_NULL: chk_access_events_manual_fields requires
    # student_id to stay set for MANUAL_BY_GUARD rows. Students are never
    # hard-deleted in this system — see Student.Status.LEFT_SCHOOL.
    student = models.ForeignKey(
        Student,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="access_events",
    )
    notes = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = schema_table("access_events")
        constraints = [
            models.CheckConstraint(
                condition=~Q(event_source="RFID_READER") | Q(reader__isnull=False),
                name="chk_access_events_rfid_fields",
            ),
            models.CheckConstraint(
                condition=~Q(event_source="MANUAL_BY_GUARD") | Q(student__isnull=False),
                name="chk_access_events_manual_fields",
            ),
        ]
        indexes = [
            models.Index(fields=["event_time"], name="idx_access_events_event_time"),
            models.Index(fields=["student", "event_time"], name="idx_access_events_student_time"),
            models.Index(fields=["reader", "event_time"], name="idx_access_events_reader_time"),
            models.Index(fields=["card", "event_time"], name="idx_access_events_card_time"),
            models.Index(fields=["event_status"], name="idx_access_events_status"),
            models.Index(
                fields=["scanned_card_uid_hash"], name="idx_access_events_uid_hash"
            ),
        ]
        ordering = ["-event_time"]

    def __str__(self) -> str:
        return f"{self.event_type} {self.event_status} @ {self.event_time}"


# ==========================================
# 12. attendance_daily
# ==========================================


class AttendanceDaily(models.Model):
    attendance_date = models.DateField()
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="attendance_records"
    )
    school_class = models.ForeignKey(
        SchoolClass,
        on_delete=models.PROTECT,
        related_name="attendance_records",
        db_column="class_id",
    )
    first_entry_time = models.DateTimeField()
    first_entry_event = models.ForeignKey(
        AccessEvent,
        on_delete=models.PROTECT,
        related_name="+",
        db_column="first_entry_event_id",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = schema_table("attendance_daily")
        constraints = [
            UniqueConstraint(
                fields=["attendance_date", "student"],
                name="uq_attendance_daily_date_student",
            ),
        ]
        indexes = [
            models.Index(fields=["attendance_date"], name="idx_attendance_daily_date"),
            models.Index(
                fields=["school_class", "attendance_date"],
                name="idx_att_daily_class_date",
            ),
            models.Index(
                fields=["student", "attendance_date"],
                name="idx_att_daily_student_date",
            ),
        ]
        ordering = ["-attendance_date"]

    def __str__(self) -> str:
        return f"{self.student} present on {self.attendance_date}"
