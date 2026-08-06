from django.urls import path

from school_access import views

app_name = "school_access"

urlpatterns = [
    path("", views.dashboard_view, name="dashboard"),
    path("students/", views.students_list_view, name="students_list"),
    path("students/new/", views.student_create_view, name="student_create"),
    path("students/<int:student_id>/edit/", views.student_edit_view, name="student_edit"),
    path("students/import/", views.students_import_view, name="students_import"),
    path("classes/", views.classes_view, name="classes"),
    path("classes/years/<int:year_id>/edit/", views.academic_year_edit_view, name="academic_year_edit"),
    path("classes/years/<int:year_id>/delete/", views.academic_year_delete_view, name="academic_year_delete"),
    path("classes/<int:class_id>/edit/", views.school_class_edit_view, name="school_class_edit"),
    path("classes/<int:class_id>/delete/", views.school_class_delete_view, name="school_class_delete"),
    path("guard/", views.guard_view, name="guard"),
    path("cards/", views.card_assignment_view, name="card_assignment"),
    path("reports/meal/", views.meal_report_view, name="meal_report"),
    path("reports/attendance/", views.attendance_report_view, name="attendance_report"),
]
