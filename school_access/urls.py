from django.urls import path

from school_access import views

app_name = "school_access"

urlpatterns = [
    path("cards/", views.card_assignment_view, name="card_assignment"),
    path("reports/meal/", views.meal_report_view, name="meal_report"),
]
