from django import forms

from school_access.models import AcademicYear, MealOption, SchoolClass, Student


class StudentForm(forms.Form):
    """Not a ModelForm: class/meal option live in separate history tables
    (StudentClassEnrollment/StudentMealAssignment), not as fields on Student."""

    last_name = forms.CharField(max_length=100)
    first_name = forms.CharField(max_length=100)
    status = forms.ChoiceField(choices=Student.Status.choices)
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


class SchoolClassForm(forms.ModelForm):
    class Meta:
        model = SchoolClass
        fields = ["academic_year", "grade", "letter", "status"]

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


class StudentImportForm(forms.Form):
    academic_year = forms.ModelChoiceField(queryset=AcademicYear.objects.all())
    csv_file = forms.FileField(label="CSV-файл")
    delimiter = forms.ChoiceField(
        choices=[(",", "Кома (,)"), (";", "Крапка з комою (;)")], initial=","
    )
