import threading

from django.core.files.storage import default_storage
from rest_framework.parsers import FormParser, MultiPartParser
from django.utils import timezone

from django.core.mail import send_mail
from django.db import transaction
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.generics import CreateAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated
from apps.users.api.serializers import RegisterSerializer, CustomTokenObtainPairSerializer, VerifyEmailSerializer, \
    UserSerializer, EmailChangeRequestOTPSerializer, \
    EmailChangeVerifyOTPSerializer, ProfilePhotoSerializer
from apps.users.models import EmailChangeOTP
from apps.users.utils import send_verification_email, generate_otp_code, hash_code, expiry
from drf_spectacular.utils import extend_schema
from rest_framework_simplejwt.views import TokenObtainPairView, TokenBlacklistView
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


class UserView(RetrieveUpdateAPIView):
    """
    API view to retrieve and update the authenticated user's details.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


@extend_schema(request=EmailChangeRequestOTPSerializer)
class EmailChangeRequestOTPView(APIView):
    """
    API view to request OTP for changing email.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = EmailChangeRequestOTPSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        new_email = ser.validated_data["new_email"]
        user = request.user

        # cooldown anti-spam
        last = EmailChangeOTP.objects.filter(user=user, new_email__iexact=new_email).order_by("-created_at").first()
        if last and (timezone.now() - last.created_at).total_seconds() < 60:
            return Response({"detail": "Espera un momento antes de solicitar otro código."}, status=429)

        code = generate_otp_code()
        EmailChangeOTP.objects.create(
            user=user,
            new_email=new_email,
            code_hash=hash_code(code),
            expires_at=expiry(10),
        )

        send_mail(
            "Tu código para cambiar el correo - Eventify",
            f"Tu código es: {code}\nVence en {10} minutos.",
            None,
            [new_email],
            fail_silently=False,
        )
        return Response({"detail": "Código enviado al nuevo correo."}, status=200)


@extend_schema(request=EmailChangeVerifyOTPSerializer)
class EmailChangeVerifyOTPView(APIView):
    """
    API view to verify OTP and change user's email.
    """
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        ser = EmailChangeVerifyOTPSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        new_email = ser.validated_data["new_email"]
        code = ser.validated_data["code"]
        user = request.user

        otp = (EmailChangeOTP.objects
               .select_for_update()
               .filter(user=user, new_email__iexact=new_email)
               .order_by("-created_at").first())

        if not otp:
            return Response({"detail": "Solicitud no encontrada."}, status=400)
        if otp.attempts >= 5:
            return Response({"detail": "Se excedieron los intentos. Solicita un nuevo código."}, status=400)
        if timezone.now() > otp.expires_at:
            return Response({"detail": "El código ha expirado. Solicita uno nuevo."}, status=400)

        otp.attempts += 1
        otp.save(update_fields=["attempts"])

        if otp.code_hash != hash_code(code):
            return Response({"detail": "Código incorrecto."}, status=400)

        user.email = new_email
        user.email_verified = True
        user.save(update_fields=["email", "email_verified"])
        EmailChangeOTP.objects.filter(user=user, new_email__iexact=new_email).delete()

        return Response({"detail": "Correo actualizado correctamente."}, status=200)


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

@extend_schema(request=ProfilePhotoSerializer)
class ProfilePhotoView(APIView):
    """
    API view to upload, update, or delete the user's profile photo.
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @transaction.atomic
    def post(self, request):
        """
        Uploads or updates the user's profile photo.
        """
        ser = ProfilePhotoSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = request.user

        old = user.profile_photo
        new_file = ser.validated_data["profile_photo"]

        user.profile_photo = new_file
        user.save(update_fields=["profile_photo"])

        if old and old.name and old.name != user.profile_photo.name:
            try:
                default_storage.delete(old.name)
            except Exception:
                pass

        return Response({
            "profile_photo": user.profile_photo.url if user.profile_photo else None
        }, status=status.HTTP_200_OK)

    @transaction.atomic
    def delete(self, request):
        """
        Deletes the user's profile photo.
        """
        user = request.user
        old = user.profile_photo
        user.profile_photo = None
        user.save(update_fields=["profile_photo"])
        if old and old.name:
            try:
                default_storage.delete(old.name)
            except Exception:
                pass
        return Response(status=status.HTTP_204_NO_CONTENT)


class LogoutView(TokenBlacklistView):
    """
    Logout view that blacklists the refresh token.
    
    POST /api/users/logout/
    """
    pass