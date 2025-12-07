from django.urls.conf import path

from apps.users.api.serializers import EmailChangeRequestOTPSerializer
from apps.users.api.views import RegisterView, LoginView, VerifyEmailView, LogoutView, UserView, \
    EmailChangeRequestOTPView, EmailChangeVerifyOTPView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('verify-email/', VerifyEmailView.as_view() , name='verify-email'),
    path("", UserView.as_view(), name="user-detail"),
    path("change-email/request/", EmailChangeRequestOTPView.as_view(), name="users-change-email"),
    path("change-email/verify/", EmailChangeVerifyOTPView.as_view(), name="users-confirm-email-change"),
]