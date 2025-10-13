from django.urls.conf import path

from apps.users.api.views import RegisterView, LoginView, VerifyEmailView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('verify-email/', VerifyEmailView.as_view() , name='verify-email'),
]