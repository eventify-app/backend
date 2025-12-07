from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.contrib.auth.models import AbstractUser

e164_validator = RegexValidator(
    regex=r'^\+[1-9]\d{1,14}$',
    message="Use formato E.164, ej: +573001234567",
)

class User(AbstractUser):
    email = models.EmailField(unique=True, db_index=True)
    phone = models.CharField(max_length=16, validators=[e164_validator], null=True, blank=True, unique=True)
    email_verified = models.BooleanField(default=False)
    date_of_birth = models.DateField(null=True, blank=True)
    profile_photo = models.CharField(max_length=255, null=True, blank=True)
    deleted_by = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='deleted_users')
    deleted_at = models.DateTimeField(null=True, blank=True)


class EmailChangeOTP(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='email_otps')
    new_email = models.EmailField()
    code_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['user', 'new_email'])]