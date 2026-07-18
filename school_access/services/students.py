"""Student CRUD, including keeping the "one active class/meal assignment"
invariant (spec sections 5.4, 5.6) in sync when a student is edited through
the UI rather than imported in bulk."""

from datetime import date

from django.db import transaction

from school_access.models import (
    MealOption,
    SchoolClass,
    Student,
    StudentClassEnrollment,
    StudentMealAssignment,
)


def _set_active_class_enrollment(student: Student, school_class: SchoolClass) -> None:
    current = StudentClassEnrollment.objects.select_for_update().filter(
        student=student, status="ACTIVE"
    ).first()
    if current is not None and current.school_class_id == school_class.id:
        return
    today = date.today()
    if current is not None:
        current.status = "ENDED"
        current.valid_to = today
        current.save(update_fields=["status", "valid_to"])
    StudentClassEnrollment.objects.create(
        student=student, school_class=school_class, valid_from=today, status="ACTIVE"
    )


def _set_active_meal_assignment(student: Student, meal_option: MealOption) -> None:
    current = StudentMealAssignment.objects.select_for_update().filter(
        student=student, status="ACTIVE"
    ).first()
    if current is not None and current.meal_option_id == meal_option.id:
        return
    today = date.today()
    if current is not None:
        current.status = "ENDED"
        current.valid_to = today
        current.save(update_fields=["status", "valid_to"])
    StudentMealAssignment.objects.create(
        student=student, meal_option=meal_option, valid_from=today, status="ACTIVE"
    )


@transaction.atomic
def create_student(
    last_name: str,
    first_name: str,
    status: str,
    school_class: SchoolClass,
    meal_option: MealOption,
) -> Student:
    student = Student.objects.create(
        last_name=last_name, first_name=first_name, status=status
    )
    _set_active_class_enrollment(student, school_class)
    _set_active_meal_assignment(student, meal_option)
    return student


@transaction.atomic
def update_student(
    student: Student,
    last_name: str,
    first_name: str,
    status: str,
    school_class: SchoolClass,
    meal_option: MealOption,
) -> Student:
    student.last_name = last_name
    student.first_name = first_name
    student.status = status
    student.save(update_fields=["last_name", "first_name", "status"])
    _set_active_class_enrollment(student, school_class)
    _set_active_meal_assignment(student, meal_option)
    return student


def current_class(student: Student) -> SchoolClass | None:
    enrollment = student.class_enrollments.filter(status="ACTIVE").select_related("school_class").first()
    return enrollment.school_class if enrollment else None


def current_meal_option(student: Student) -> MealOption | None:
    assignment = student.meal_assignments.filter(status="ACTIVE").select_related("meal_option").first()
    return assignment.meal_option if assignment else None
