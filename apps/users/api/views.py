import threading

from django.db import transaction
from django.contrib.auth import get_user_model
from rest_framework.generics import CreateAPIView
from apps.users.api.serializers import RegisterSerializer
from apps.users.utils import send_verification_email

User = get_user_model()

def _send_verification_async(user):
    """
    Send a verification email to the user asynchronously.
    :param user:  User instance
    :return: None
    """
    threading.Thread(target=send_verification_email, args=(user,), daemon=True).start()

class RegisterView(CreateAPIView):
    """
    API view to handle user registration.
    """
    serializer_class = RegisterSerializer
    queryset = User.objects.all()

    def perform_create(self, serializer):
        """
        Save the new user and send a verification email asynchronously after the transaction is committed.
        """
        user = serializer.save()
        transaction.on_commit(lambda : _send_verification_async(user))

