from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsInAdministratorGroup(BasePermission):
    """
    Allows access only to users in the "Administrator" group.
    """
    message = "Se requiere pertenecer al grupo Administrator."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return user.groups.filter(name="Administrator").exists()