from django.contrib import admin

from school_access.models import (
    AcademicYear,
    AccessEvent,
    AttendanceDaily,
    DailyReportSettings,
    MealOption,
    ReaderLocation,
    RfidCard,
    RfidCardAssignment,
    RfidReader,
    SchoolClass,
    Student,
    StudentClassEnrollment,
    StudentMealAssignment,
)


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ("name", "starts_on", "ends_on", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)
    ordering = ("-starts_on",)


@admin.register(SchoolClass)
class SchoolClassAdmin(admin.ModelAdmin):
    list_display = ("name", "grade", "letter", "academic_year", "status")
    list_filter = ("academic_year", "status")
    search_fields = ("name",)
    ordering = ("academic_year", "grade", "letter")


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("last_name", "first_name", "status", "current_class")
    list_filter = ("status",)
    search_fields = ("last_name", "first_name")
    ordering = ("last_name", "first_name")

    @admin.display(description="Class")
    def current_class(self, obj: Student):
        enrollment = obj.class_enrollments.filter(status="ACTIVE").first()
        return enrollment.school_class if enrollment else "-"


@admin.register(StudentClassEnrollment)
class StudentClassEnrollmentAdmin(admin.ModelAdmin):
    list_display = ("student", "school_class", "valid_from", "valid_to", "status")
    list_filter = ("status", "school_class")
    search_fields = ("student__last_name", "student__first_name")
    ordering = ("-valid_from",)


@admin.register(MealOption)
class MealOptionAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")


@admin.register(StudentMealAssignment)
class StudentMealAssignmentAdmin(admin.ModelAdmin):
    list_display = ("student", "meal_option", "valid_from", "valid_to", "status")
    list_filter = ("status", "meal_option")
    search_fields = ("student__last_name", "student__first_name")
    ordering = ("-valid_from",)


@admin.register(RfidCard)
class RfidCardAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "deactivated_at", "deactivation_reason")
    list_filter = ("status",)
    readonly_fields = ("card_uid_hash",)
    ordering = ("-id",)


@admin.register(RfidCardAssignment)
class RfidCardAssignmentAdmin(admin.ModelAdmin):
    list_display = ("card", "student", "assigned_from", "assigned_to", "status", "end_reason")
    list_filter = ("status", "end_reason")
    search_fields = ("student__last_name", "student__first_name")
    ordering = ("-assigned_from",)


@admin.register(ReaderLocation)
class ReaderLocationAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name",)


@admin.register(RfidReader)
class RfidReaderAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "location", "purpose", "status")
    list_filter = ("purpose", "status", "location")
    search_fields = ("code", "name")
    ordering = ("code",)


@admin.register(AccessEvent)
class AccessEventAdmin(admin.ModelAdmin):
    list_display = (
        "event_time",
        "event_type",
        "event_source",
        "event_status",
        "student",
        "reader",
    )
    list_filter = ("event_type", "event_source", "event_status", "reader")
    search_fields = ("student__last_name", "student__first_name", "scanned_card_uid_hash")
    ordering = ("-event_time",)
    date_hierarchy = "event_time"

    fieldsets = (
        ("Event", {"fields": ("event_time", "event_type", "event_source", "event_status")}),
        ("Source", {"fields": ("reader", "scanned_card_uid_hash", "card", "card_assignment")}),
        ("Result", {"fields": ("student", "notes")}),
    )


@admin.register(AttendanceDaily)
class AttendanceDailyAdmin(admin.ModelAdmin):
    list_display = (
        "attendance_date",
        "student",
        "school_class",
        "first_entry_time",
        "last_entry_time",
        "last_exit_time",
    )
    list_filter = ("school_class",)
    search_fields = ("student__last_name", "student__first_name")
    ordering = ("-attendance_date",)
    date_hierarchy = "attendance_date"


@admin.register(DailyReportSettings)
class DailyReportSettingsAdmin(admin.ModelAdmin):
    list_display = ("send_time", "is_enabled", "last_sent_on", "updated_at")
