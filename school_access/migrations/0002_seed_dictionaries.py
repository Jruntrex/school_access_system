from django.db import migrations


def seed(apps, schema_editor):
    MealOption = apps.get_model("school_access", "MealOption")
    ReaderLocation = apps.get_model("school_access", "ReaderLocation")
    RfidReader = apps.get_model("school_access", "RfidReader")

    MealOption.objects.get_or_create(code="STANDARD", defaults={"name": "Стандартне харчування"})
    MealOption.objects.get_or_create(code="NO_MEAL", defaults={"name": "Не харчується"})
    MealOption.objects.get_or_create(code="SPECIAL", defaults={"name": "Окремий варіант харчування"})

    vestibule, _ = ReaderLocation.objects.get_or_create(
        name="Вестибюль", defaults={"description": "Зона входу до школи"}
    )
    ReaderLocation.objects.get_or_create(
        name="Їдальня", defaults={"description": "Шкільна їдальня"}
    )

    RfidReader.objects.get_or_create(
        code="VESTIBULE_ENTRY_1",
        defaults={
            "name": "Зчитувач на вході (вестибюль) 1",
            "location": vestibule,
            "purpose": "ENTER_SCHOOL",
            "status": "ACTIVE",
        },
    )


def unseed(apps, schema_editor):
    MealOption = apps.get_model("school_access", "MealOption")
    ReaderLocation = apps.get_model("school_access", "ReaderLocation")
    RfidReader = apps.get_model("school_access", "RfidReader")

    RfidReader.objects.filter(code="VESTIBULE_ENTRY_1").delete()
    ReaderLocation.objects.filter(name__in=["Вестибюль", "Їдальня"]).delete()
    MealOption.objects.filter(code__in=["STANDARD", "NO_MEAL", "SPECIAL"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("school_access", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
