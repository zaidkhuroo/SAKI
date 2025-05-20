from django.urls import path
from .views import (
    UserRegistrationView,
    UserLoginView,
    UserLogoutView,
    UserInfoView,
    AdminUserView,
    AdminUserDetailView,
    GoogleLogin
)

urlpatterns = [
    path('auth/google/', GoogleLogin.as_view(), name='google_login'),
    path('register/', UserRegistrationView.as_view(), name='register'),
    path('login/', UserLoginView.as_view(), name='login'),
    path('logout/', UserLogoutView.as_view(), name='logout'),
    path('info/', UserInfoView.as_view(), name='user-info'),
    path('admin-users/', AdminUserView.as_view(), name='admin-users'),
    path('admin-users/<int:user_id>/', AdminUserDetailView.as_view(), name='admin-user-detail'),
]
