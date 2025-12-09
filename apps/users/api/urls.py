from django.urls.conf import path

from apps.users.api.views import RegisterView, LoginView, VerifyEmailView, LogoutView, UserStatusUpdateView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('verify-email/', VerifyEmailView.as_view() , name='verify-email'),
    path('disable/<int:pk>/', UserStatusUpdateView.as_view(), name='user-status-update'),
]