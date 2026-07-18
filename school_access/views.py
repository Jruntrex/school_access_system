import csv
from datetime import date as date_cls

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from school_access import selectors
from school_access.forms import (
    AcademicYearForm,
    SchoolClassForm,
    StudentForm,
    StudentImportForm,
)
from school_access.models import AcademicYear, AccessEvent, RfidCardAssignment, SchoolClass, Student
from school_access.services import students as students_service
from school_access.services.imports import import_students, parse_csv_rows


@staff_member_required
def dashboard_view(request):
    today = date_cls.today()

    present_count = len(selectors.present_students(today))
    absent_count = len(selectors.absent_students(today))
    meal_count = len(selectors.daily_meal_report(today))
    no_card_count = len(selectors.students_without_active_card())
    problematic_today = (
        selectors.problematic_card_events().filter(event_time__date=today).count()
    )

    context = {
        "active_page": "dashboard",
        "today": today,
        "present_count": present_count,
        "absent_count": absent_count,
        "meal_count": meal_count,
        "no_card_count": no_card_count,
        "problematic_today": problematic_today,
    }
    return render(request, "school_access/dashboard.html", context)


@staff_member_required
def card_assignment_view(request):
    students = (
        Student.objects.filter(status=Student.Status.ACTIVE)
        .select_related()
        .prefetch_related("class_enrollments__school_class", "card_assignments")
        .order_by("last_name", "first_name")
    )

    rows = []
    for student in students:
        enrollment = next(
            (e for e in student.class_enrollments.all() if e.status == "ACTIVE"), None
        )
        assignment = next(
            (a for a in student.card_assignments.all() if a.status == "ACTIVE"), None
        )
        rows.append(
            {
                "student": student,
                "school_class": enrollment.school_class if enrollment else None,
                "has_card": assignment is not None,
            }
        )

    context = {
        "active_page": "cards",
        "rows": rows,
        "end_reasons": RfidCardAssignment.EndReason.choices,
    }
    return render(request, "school_access/card_assignment.html", context)


@staff_member_required
def meal_report_view(request):
    report_date_str = request.GET.get("date")
    report_date = (
        date_cls.fromisoformat(report_date_str) if report_date_str else date_cls.today()
    )
    rows = list(selectors.daily_meal_report(report_date))

    if request.GET.get("format") == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="meal_report_{report_date}.csv"'
        writer = csv.writer(response)
        writer.writerow(["Class", "Last name", "First name", "Entry time", "Meal option"])
        for row in rows:
            writer.writerow(
                [
                    row["school_class__name"],
                    row["student__last_name"],
                    row["student__first_name"],
                    row["first_entry_time"],
                    row["student__meal_assignments__meal_option__name"],
                ]
            )
        return response

    context = {"active_page": "meal_report", "report_date": report_date, "rows": rows}
    return render(request, "school_access/meal_report.html", context)


@staff_member_required
def students_list_view(request):
    students = (
        Student.objects.all()
        .prefetch_related("class_enrollments__school_class", "meal_assignments__meal_option")
        .order_by("last_name", "first_name")
    )

    rows = [
        {
            "student": student,
            "school_class": students_service.current_class(student),
            "meal_option": students_service.current_meal_option(student),
        }
        for student in students
    ]

    context = {"active_page": "students", "rows": rows}
    return render(request, "school_access/students_list.html", context)


@staff_member_required
def student_create_view(request):
    if request.method == "POST":
        form = StudentForm(request.POST)
        if form.is_valid():
            students_service.create_student(
                last_name=form.cleaned_data["last_name"],
                first_name=form.cleaned_data["first_name"],
                status=form.cleaned_data["status"],
                school_class=form.cleaned_data["school_class"],
                meal_option=form.cleaned_data["meal_option"],
            )
            messages.success(request, "Учня додано.")
            return redirect("school_access:students_list")
    else:
        form = StudentForm(initial={"status": Student.Status.ACTIVE})

    context = {"active_page": "students", "form": form, "is_new": True}
    return render(request, "school_access/student_form.html", context)


@staff_member_required
def student_edit_view(request, student_id):
    student = get_object_or_404(Student, pk=student_id)

    if request.method == "POST":
        form = StudentForm(request.POST)
        if form.is_valid():
            students_service.update_student(
                student,
                last_name=form.cleaned_data["last_name"],
                first_name=form.cleaned_data["first_name"],
                status=form.cleaned_data["status"],
                school_class=form.cleaned_data["school_class"],
                meal_option=form.cleaned_data["meal_option"],
            )
            messages.success(request, "Дані учня оновлено.")
            return redirect("school_access:students_list")
    else:
        form = StudentForm(
            initial={
                "last_name": student.last_name,
                "first_name": student.first_name,
                "status": student.status,
                "school_class": students_service.current_class(student),
                "meal_option": students_service.current_meal_option(student),
            }
        )

    context = {
        "active_page": "students",
        "form": form,
        "is_new": False,
        "student": student,
    }
    return render(request, "school_access/student_form.html", context)


@staff_member_required
def students_import_view(request):
    result = None
    if request.method == "POST":
        form = StudentImportForm(request.POST, request.FILES)
        if form.is_valid():
            rows = parse_csv_rows(
                form.cleaned_data["csv_file"].file, delimiter=form.cleaned_data["delimiter"]
            )
            result = import_students(rows, form.cleaned_data["academic_year"])
    else:
        form = StudentImportForm()

    context = {"active_page": "students", "form": form, "result": result}
    return render(request, "school_access/students_import.html", context)


@staff_member_required
def classes_view(request):
    if request.method == "POST":
        if request.POST.get("form") == "academic_year":
            year_form = AcademicYearForm(request.POST)
            class_form = SchoolClassForm()
            if year_form.is_valid():
                year_form.save()
                messages.success(request, "Навчальний рік додано.")
                return redirect("school_access:classes")
        else:
            class_form = SchoolClassForm(request.POST)
            year_form = AcademicYearForm()
            if class_form.is_valid():
                class_form.save()
                messages.success(request, "Клас додано.")
                return redirect("school_access:classes")
    else:
        year_form = AcademicYearForm()
        class_form = SchoolClassForm()

    context = {
        "active_page": "classes",
        "year_form": year_form,
        "class_form": class_form,
        "academic_years": AcademicYear.objects.all(),
        "classes": SchoolClass.objects.select_related("academic_year").all(),
    }
    return render(request, "school_access/classes.html", context)


@staff_member_required
def guard_view(request):
    students = (
        Student.objects.filter(status=Student.Status.ACTIVE)
        .prefetch_related("class_enrollments__school_class")
        .order_by("last_name", "first_name")
    )
    rows = [
        {"student": student, "school_class": students_service.current_class(student)}
        for student in students
    ]

    recent_entries = (
        AccessEvent.objects.filter(
            event_source=AccessEvent.EventSource.MANUAL_BY_GUARD,
            event_time__date=date_cls.today(),
        )
        .select_related("student")
        .order_by("-event_time")[:20]
    )

    context = {"active_page": "guard", "rows": rows, "recent_entries": recent_entries}
    return render(request, "school_access/guard.html", context)
