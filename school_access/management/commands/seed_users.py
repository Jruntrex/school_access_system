"""Creates (or resets the password of) the two hardcoded accounts this app
uses instead of self-service registration: an admin (full CRUD access,
also usable at /admin/) and a guard/staff account (dashboard only — see
school_access/auth.py). Safe to re-run; existing accounts are updated,
not duplicated.

Usage:
    python manage.py seed_users
    python manage.py seed_users --admin-password "NewPass123" --guard-password "NewPass456"
"""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "Admin#2026"
DEFAULT_GUARD_USERNAME = "guard"
DEFAULT_GUARD_PASSWORD = "Guard#2026"


class Command(BaseCommand):
    help = "Seed the two hardcoded accounts (admin + guard) with fixed credentials"

    def add_arguments(self, parser):
        parser.add_argument("--admin-username", default=DEFAULT_ADMIN_USERNAME)
        parser.add_argument("--admin-password", default=DEFAULT_ADMIN_PASSWORD)
        parser.add_argument("--guard-username", default=DEFAULT_GUARD_USERNAME)
        parser.add_argument("--guard-password", default=DEFAULT_GUARD_PASSWORD)

    def handle(self, *args, **options):
        admin_user, created = User.objects.get_or_create(
            username=options["admin_username"],
            defaults={"is_staff": True, "is_superuser": True},
        )
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.set_password(options["admin_password"])
        admin_user.save()
        self.stdout.write(
            self.style.SUCCESS(
                f"{'Створено' if created else 'Оновлено'} адміна: "
                f"{options['admin_username']} / {options['admin_password']}"
            )
        )

        guard_user, created = User.objects.get_or_create(
            username=options["guard_username"],
            defaults={"is_staff": False, "is_superuser": False},
        )
        guard_user.is_staff = False
        guard_user.is_superuser = False
        guard_user.set_password(options["guard_password"])
        guard_user.save()
        self.stdout.write(
            self.style.SUCCESS(
                f"{'Створено' if created else 'Оновлено'} охорону: "
                f"{options['guard_username']} / {options['guard_password']}"
            )
        )

        self.stdout.write(
            self.style.WARNING(
                "Це хардкоджені паролі для локального використання в школі — "
                "зміни їх через /admin/ або повторний запуск цієї команди з "
                "--admin-password / --guard-password."
            )
        )
