import threading

from django.db import transaction
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.generics import CreateAPIView
from apps.users.api.serializers import RegisterSerializer,CustomTokenObtainPairSerializer, VerifyEmailSerializer
from apps.users.utils import send_verification_email
from drf_spectacular.utils import extend_schema
from rest_framework_simplejwt.views import TokenObtainPairView
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.contrib.auth.tokens import PasswordResetTokenGenerator

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

@extend_schema(tags=["auth"])
class LoginView(TokenObtainPairView):
    """
    API view to handle user login and obtain JWT tokens.
    """
    serializer_class = CustomTokenObtainPairSerializer

@extend_schema(tags=['auth'])
class VerifyEmailView(APIView): # aqui heredo de APIView de drf

    serializer_class = VerifyEmailSerializer

    def post(self, request): #como herede entonces este request es de drf
        serializer = VerifyEmailSerializer(data = request.data) #request trae un json y yo cojo los todos los datos, tambien podria hacer algo como request.data.get('token')

        if not serializer.is_valid():
            return Response(
                {"error": "Datos inválidos", "details": serializer.errors},
                status = status.HTTP_400_BAD_REQUEST
            )

        uid = request.data.get('uid')
        token = request.data.get('token')

        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk = user_id)

            token_generator = PasswordResetTokenGenerator() # para recalcular el token y validar si es correcto o no

            if not token_generator.check_token(user, token):
                return Response(
                    {"error": "Token inválido o expirado"},
                    status = status.HTTP_400_BAD_REQUEST
                )
            
            if user.email_verified:
                return Response(
                    {"message": "El email ya ha sido verificado anteriormente"},
                    status = status.HTTP_200_OK
                )
            
            user.email_verified = True
            user.save(update_fields=['email_verified'])

            return Response(
                {"message": "Email verificado exitosamente"},
                status = status.HTTP_200_OK
            )
        
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response(
                {"error": "Usuario no encontrado o uid inválido"},
                status = status.HTTP_400_BAD_REQUEST
            )
