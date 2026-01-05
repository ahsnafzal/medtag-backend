from django.urls import path
from .views import (
    CreateUserView, 
    LoginAPIView, 
    GetUserProfileView,
    ProfileUpdateAPIView, 
    ChangePasswordAPIView,
    PasswordResetRequestView, 
    ResetPasswordAPIView,
    ContactUSView,
    DoctorDashboardAPIView, 
    VerifyEmailAPIView,
    PatientProfileView,
    PatientDashboardAPIView,
    DoctorListView,  # ✅ Added
    DoctorDetailView # ✅ Added
    
)

urlpatterns = [
    # Auth
    path('register/', CreateUserView.as_view(), name='signup'),
    path('verify-email/', VerifyEmailAPIView.as_view(), name='verify-email'),
    path('login/', LoginAPIView.as_view(), name='login'),
    
    # Profile
    path('profile/', GetUserProfileView.as_view(), name='profile'),
    path('profile/update/', ProfileUpdateAPIView.as_view(), name='profile-update'),
    path('change/password/', ChangePasswordAPIView.as_view(), name='change-password'),
    
    # Password Reset
    path('forgot-password/', PasswordResetRequestView.as_view(), name='forget-password'),
    path('reset-password/', ResetPasswordAPIView.as_view(), name='reset-password'),
    
    # General
    path('contactus/', ContactUSView.as_view(), name='contactus'),
    
    # Dashboards
    path('doctor/dashboard/', DoctorDashboardAPIView.as_view(), name='doctor-dashboard'),
    path('patient/profile/', PatientProfileView.as_view(), name='patient-profile'),
    
    # ✅ DOCTOR LIST (For Patient Dashboard)
    path('doctors/', DoctorListView.as_view(), name='doctor-list'),
    path('doctors/<int:pk>/', DoctorDetailView.as_view(), name='doctor-detail'),


]