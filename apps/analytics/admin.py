from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from apps.users.models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    # columnas y filtros que ya tenías
    list_display = ('id', 'username', 'first_name', 'last_name', 'email', 'is_staff', 'is_active', 'date_joined')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    list_filter = ('is_staff', 'is_active', 'date_joined')

    # secciones del formulario de edición
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Información personal'),
         {'fields': ('first_name', 'last_name', 'email', 'phone', 'date_of_birth', 'profile_photo')}),
        (_('Permisos'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Fechas importantes'), {'fields': ('last_login', 'date_joined', 'deleted_at')}),
    )

    # formulario de creación (incluye password1/2)
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
            'username', 'email', 'first_name', 'last_name', 'password1', 'password2', 'is_active', 'is_staff',
            'groups'),
        }),
    )

    # hace que “groups” y “user_permissions” usen el selector horizontal
    filter_horizontal = ('groups', 'user_permissions')