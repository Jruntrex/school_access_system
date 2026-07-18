import csv
from datetime import date as date_cls

from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse
from django.shortcuts import render

from school_access import selectors
from school_access.models import RfidCardAssignment, Student


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
