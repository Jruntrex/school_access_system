from django import forms

from school_access.models import (
    AcademicYear,
    DailyReportSettings,
    MealOption,
    SchoolClass,
    Student,
)


class StudentForm(forms.Form):
    """Not a ModelForm: class/meal option live in separate history tables
    (StudentClassEnrollment/StudentMealAssignment), not as fields on Student."""

    last_name = forms.CharField(max_length=100, label="Прізвище")
    first_name = forms.CharField(max_length=100, label="Ім'я")
    status = forms.ChoiceField(choices=Student.Status.choices, label="Статус")
    school_class = forms.ModelChoiceField(
        queryset=SchoolClass.objects.filter(status="ACTIVE"),
        label="Клас",
    )
    meal_option = forms.ModelChoiceField(
        queryset=MealOption.objects.filter(is_active=True),
        label="Харчування",
    )


class AcademicYearForm(forms.ModelForm):
    class Meta:
        model = AcademicYear
        fields = ["name", "starts_on", "ends_on", "is_active"]
        widgets = {
            "starts_on": forms.DateInput(attrs={"type": "date"}),
            "ends_on": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "name": "Назва",
            "starts_on": "Дата початку",
            "ends_on": "Дата завершення",
            "is_active": "Активний",
        }


class SchoolClassForm(forms.ModelForm):
    class Meta:
        model = SchoolClass
        fields = ["academic_year", "grade", "letter", "status"]
        labels = {
            "academic_year": "Навчальний рік",
            "grade": "Клас (номер)",
            "letter": "Літера",
            "status": "Статус",
        }

    def clean(self):
        cleaned = super().clean()
        grade = cleaned.get("grade")
        letter = cleaned.get("letter")
        if grade and letter:
            cleaned["name"] = f"{grade}-{letter}"
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.name = f"{instance.grade}-{instance.letter}"
        if commit:
            instance.save()
        return instance


class DailyReportSettingsForm(forms.ModelForm):
    class Meta:
        model = DailyReportSettings
        fields = ["send_time", "is_enabled"]
        widgets = {
            "send_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
        }
        labels = {
            "send_time": "Час надсилання звіту",
            "is_enabled": "Щоденний звіт увімкнено",
        }


class StudentImportForm(forms.Form):
    academic_year = forms.ModelChoiceField(
        queryset=AcademicYear.objects.all(), label="Навчальний рік"
    )
    csv_file = forms.FileField(label="CSV-файл")
    delimiter = forms.ChoiceField(
        choices=[(",", "Кома (,)"), (";", "Крапка з комою (;)")],
        initial=",",
        label="Роздільник",
    )
