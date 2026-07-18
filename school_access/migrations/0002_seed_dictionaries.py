from django.db import migrations


def seed(apps, schema_editor):
    MealOption = apps.get_model("school_access", "MealOption")
    ReaderLocation = apps.get_model("school_access", "ReaderLocation")
    RfidReader = apps.get_model("school_access", "RfidReader")

    MealOption.objects.get_or_create(code="STANDARD", defaults={"name": "Standard meal"})
    MealOption.objects.get_or_create(code="NO_MEAL", defaults={"name": "No meal"})
    MealOption.objects.get_or_create(code="SPECIAL", defaults={"name": "Special meal option"})

    vestibule, _ = ReaderLocation.objects.get_or_create(
        name="Vestibule", defaults={"description": "School entry area"}
    )
    ReaderLocation.objects.get_or_create(
        name="Canteen", defaults={"description": "School canteen"}
    )

    RfidReader.objects.get_or_create(
        code="VESTIBULE_ENTRY_1",
        defaults={
            "name": "Vestibule Entry Reader 1",
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
    ReaderLocation.objects.filter(name__in=["Vestibule", "Canteen"]).delete()
    MealOption.objects.filter(code__in=["STANDARD", "NO_MEAL", "SPECIAL"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("school_access", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
