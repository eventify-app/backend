from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
import os

User = get_user_model()

class Command(BaseCommand):
    help = "Crea (si no existe) un admin de negocio y asegura grupos por defecto."

    def handle(self, *args, **opts):
        admin_group, _ = Group.objects.get_or_create(name="Administrator")
        Group.objects.get_or_create(name="Student")

        username = os.getenv("ADMIN_USERNAME")
        email    = os.getenv("ADMIN_EMAIL")
        password = os.getenv("ADMIN_PASSWORD")

        if not (username and email and password):
            self.stdout.write(self.style.WARNING(
                "Faltan ADMIN_USERNAME/ADMIN_EMAIL/ADMIN_PASSWORD. No se creó usuario."
            ))
            return

        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": email, "is_active": True}
        )
        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Admin creado: {username}"))

        if not user.groups.filter(name="Administrator").exists():
            user.groups.add(admin_group)

        if hasattr(user, "email_verified") and not user.email_verified:
            user.email_verified = True
            user.save(update_fields=["email_verified"])

        self.stdout.write(self.style.SUCCESS("Bootstrap de admin completado."))