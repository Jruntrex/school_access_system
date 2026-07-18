from django.db import models
from django.db.models import Q, UniqueConstraint

# ==========================================
# Shared status vocabularies (see spec section 5)
# ==========================================


class ActiveEndedStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    ENDED = "ENDED", "Ended"


# ==========================================
# 5.1 academic_years
# ==========================================


class AcademicYear(models.Model):
    name = models.CharField(max_length=20, unique=True)
    starts_on = models.DateField()
    ends_on = models.DateField()
    is_active = models.BooleanField(default=False)

    class Meta:
        db_table = "academic_years"
        constraints = [
            models.CheckConstraint(
                condition=Q(starts_on__lt=models.F("ends_on")),
                name="academic_year_starts_before_ends",
            ),
        ]
        ordering = ["-starts_on"]

    def __str__(self) -> str:
        return self.name


# ==========================================
# 5.2 classes
# ==========================================


class SchoolClass(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"

    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.PROTECT, related_name="classes"
    )
    grade = models.PositiveSmallIntegerField()
    letter = models.CharField(max_length=8)
    name = models.CharField(max_length=20)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.ACTIVE
    )

    class Meta:
        db_table = "classes"
        constraints = [
            UniqueConstraint(
                fields=["academic_year", "grade", "letter"],
                name="unique_class_per_academic_year",
            ),
        ]
        indexes = [
            models.Index(fields=["academic_year"], name="idx_classes_academic_year"),
        ]
        ordering = ["grade", "letter"]

    def __str__(self) -> str:
        return self.name


# ==========================================
# 5.3 students
# ==========================================


class Student(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"
        LEFT_SCHOOL = "LEFT_SCHOOL", "Left school"

    last_name = models.CharField(max_length=100)
    first_name = models.CharField(max_length=100)
    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.ACTIVE
    )

    class Meta:
        db_table = "students"
        indexes = [
            models.Index(fields=["last_name", "first_name"], name="idx_students_name"),
        ]
        ordering = ["last_name", "first_name"]

    def __str__(self) -> str:
        return f"{self.last_name} {self.first_name}"


# ==========================================
# 5.4 student_class_enrollments
# ==========================================


class StudentClassEnrollment(models.Model):
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="class_enrollments"
    )
    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.PROTECT, related_name="enrollments"
    )
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=10,
        choices=ActiveEndedStatus.choices,
        default=ActiveEndedStatus.ACTIVE,
    )

    class Meta:
        db_table = "student_class_enrollments"
        constraints = [
            UniqueConstraint(
                fields=["student"],
                condition=Q(status="ACTIVE"),
                name="unique_active_class_enrollment_per_student",
            ),
        ]
        indexes = [
            models.Index(fields=["school_class"], name="idx_enrollments_class"),
        ]
        ordering = ["-valid_from"]

    def __str__(self) -> str:
        return f"{self.student} -> {self.school_class} ({self.status})"


# ==========================================
# 5.5 meal_options
# ==========================================


class MealOption(models.Model):
    STANDARD = "STANDARD"
    NO_MEAL = "NO_MEAL"
    SPECIAL = "SPECIAL"

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)

    class Meta:
        db_table = "meal_options"
        ordering = ["code"]

    def __str__(self) -> str:
        return self.name


# ==========================================
# 5.6 student_meal_assignments
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
        max_length=10,
        choices=ActiveEndedStatus.choices,
        default=ActiveEndedStatus.ACTIVE,
    )

    class Meta:
        db_table = "student_meal_assignments"
        constraints = [
            UniqueConstraint(
                fields=["student"],
                condition=Q(status="ACTIVE"),
                name="unique_active_meal_assignment_per_student",
            ),
        ]
        ordering = ["-valid_from"]

    def __str__(self) -> str:
        return f"{self.student} -> {self.meal_option} ({self.status})"


# ==========================================
# 5.7 rfid_cards
# ==========================================


class RfidCard(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        LOST = "LOST", "Lost"
        DAMAGED = "DAMAGED", "Damaged"
        RETIRED = "RETIRED", "Retired"

    card_uid_hash = models.CharField(max_length=64, unique=True)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.ACTIVE
    )
    deactivated_at = models.DateTimeField(null=True, blank=True)
    deactivation_reason = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table = "rfid_cards"
        ordering = ["-id"]

    def __str__(self) -> str:
        return f"Card #{self.pk} ({self.status})"


# ==========================================
# 5.8 rfid_card_assignments
# ==========================================


class RfidCardAssignment(models.Model):
    class EndReason(models.TextChoices):
        LOST = "LOST", "Lost"
        DAMAGED = "DAMAGED", "Damaged"
        REPLACED = "REPLACED", "Replaced"
        STUDENT_LEFT = "STUDENT_LEFT", "Student left"
        OTHER = "OTHER", "Other"

    card = models.ForeignKey(
        RfidCard, on_delete=models.CASCADE, related_name="assignments"
    )
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="card_assignments"
    )
    assigned_from = models.DateTimeField()
    assigned_to = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=10,
        choices=ActiveEndedStatus.choices,
        default=ActiveEndedStatus.ACTIVE,
    )
    end_reason = models.CharField(
        max_length=20, choices=EndReason.choices, blank=True
    )

    class Meta:
        db_table = "rfid_card_assignments"
        constraints = [
            UniqueConstraint(
                fields=["card"],
                condition=Q(status="ACTIVE"),
                name="unique_active_assignment_per_card",
            ),
            UniqueConstraint(
                fields=["student"],
                condition=Q(status="ACTIVE"),
                name="unique_active_assignment_per_student",
            ),
        ]
        ordering = ["-assigned_from"]

    def __str__(self) -> str:
        return f"{self.card} -> {self.student} ({self.status})"


# ==========================================
# 5.9 reader_locations
# ==========================================


class ReaderLocation(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "reader_locations"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


# ==========================================
# 5.10 rfid_readers
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
    purpose = models.CharField(max_length=15, choices=Purpose.choices)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.ACTIVE
    )

    class Meta:
        db_table = "rfid_readers"
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} ({self.get_purpose_display()})"


# ==========================================
# 5.11 access_events
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
    event_type = models.CharField(max_length=15, choices=EventType.choices)
    event_source = models.CharField(max_length=20, choices=EventSource.choices)
    event_status = models.CharField(max_length=25, choices=EventStatus.choices)

    reader = models.ForeignKey(
        RfidReader,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )
    scanned_card_uid_hash = models.CharField(max_length=64, null=True, blank=True)
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
    student = models.ForeignKey(
        Student,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="access_events",
    )
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "access_events"
        indexes = [
            models.Index(fields=["event_time"], name="idx_events_time"),
            models.Index(fields=["student", "event_time"], name="idx_events_student_time"),
            models.Index(fields=["reader", "event_time"], name="idx_events_reader_time"),
            models.Index(fields=["card", "event_time"], name="idx_events_card_time"),
            models.Index(
                fields=["scanned_card_uid_hash"], name="idx_events_scanned_hash"
            ),
        ]
        ordering = ["-event_time"]

    def __str__(self) -> str:
        return f"{self.event_type} {self.event_status} @ {self.event_time}"


# ==========================================
# 5.12 attendance_daily
# ==========================================


class AttendanceDaily(models.Model):
    attendance_date = models.DateField()
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="attendance_records"
    )
    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.PROTECT, related_name="attendance_records"
    )
    first_entry_time = models.DateTimeField()
    first_entry_event = models.ForeignKey(
        AccessEvent, on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        db_table = "attendance_daily"
        constraints = [
            UniqueConstraint(
                fields=["attendance_date", "student"],
                name="unique_attendance_per_day",
            ),
        ]
        indexes = [
            models.Index(fields=["attendance_date"], name="idx_attendance_date"),
            models.Index(
                fields=["school_class", "attendance_date"],
                name="idx_attendance_class_date",
            ),
            models.Index(
                fields=["student", "attendance_date"],
                name="idx_attendance_student_date",
            ),
        ]
        ordering = ["-attendance_date"]

    def __str__(self) -> str:
        return f"{self.student} present on {self.attendance_date}"
