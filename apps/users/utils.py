from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

token_generator = PasswordResetTokenGenerator()

def send_verification_email(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = token_generator.make_token(user)
    verification_link = f"{settings.FRONTEND_URL}/verify-email?uid={uid}&token={token}"

    subject = "Confirma tu correo - Eventify"
    body = (
        f"Hola {user.first_name or user.username},\n\n"
        f"Gracias por registrarte en Eventify. Por favor, confirma tu correo electrónico haciendo clic en el siguiente enlace:\n\n"
        f"{verification_link}\n\n"
        "Si no te has registrado en Eventify, puedes ignorar este correo.\n\n"
        "Saludos,\nEl equipo de Eventify"
    )

    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)