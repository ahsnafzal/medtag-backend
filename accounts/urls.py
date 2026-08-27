from django.urls import path

from .views import (
    PatientAppointmentsView,
    ProcessPaymentView,
    ConfirmPaymentView,
    JazzCashCheckoutLinkView,
    ChatAPIView,
    DocumentUploadView,
    DocumentDeleteView,

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

    DoctorListView,
    DoctorDetailView,

    BookAppointmentView,
    BookedSlotsView,
    UpdateAppointmentStatusView,
    CancelAppointmentView,
    RescheduleAppointmentView,
    UpdateAppointmentRecordView,
    DoctorPayoutMethodView,
    GenerateStripeLinkView,
    VerifyStripeAccountView,
    DoctorEarningsAnalyticsView,
    RequestWithdrawalView,
    AdminUserManagementView,
    AdminUserDetailView,
    AdminOverviewView,
    AdminAppointmentManagementView,
    AdminPaymentDecisionView,
    AdminChatMessageManagementView,
    ReserveCallSlotView,
    ReleaseCallSlotView,
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

    # Doctors
    path('doctors/', DoctorListView.as_view(), name='doctor-list'),
    path('doctors/<int:pk>/', DoctorDetailView.as_view(), name='doctor-detail'),

    # Appointments
    path('appointments/book/', BookAppointmentView.as_view(), name='book-appointment'),
    path('appointments/booked-slots/', BookedSlotsView.as_view(), name='booked-slots'),
    path('appointments/<int:pk>/status/', UpdateAppointmentStatusView.as_view(), name='update-appointment-status'),
    path('appointments/<int:pk>/cancel/', CancelAppointmentView.as_view(), name='cancel-appointment'),
    path('appointments/<int:pk>/reschedule/', RescheduleAppointmentView.as_view(), name='reschedule-appointment'),
    path('appointments/<int:pk>/record/', UpdateAppointmentRecordView.as_view(), name='update-appointment-record'),
    path('patient/appointments/', PatientAppointmentsView.as_view(), name='patient-appointments'),
    path('appointments/<int:pk>/pay/', ProcessPaymentView.as_view(), name='process-payment'),
    path('appointments/<int:pk>/confirm-payment/', ConfirmPaymentView.as_view(), name='confirm-payment'),
    path(
        'appointments/<int:pk>/jazzcash-checkout-link/',
        JazzCashCheckoutLinkView.as_view(),
        name='jazzcash-checkout-link',
    ),

    path('call/reserve-slot/', ReserveCallSlotView.as_view(), name='call-reserve-slot'),
    path('call/release-slot/', ReleaseCallSlotView.as_view(), name='call-release-slot'),
    
    # Chat
    path('appointments/<int:pk>/chat/', ChatAPIView.as_view(), name='chat'),

    # Doctor Payout & Earnings
    path('doctor/payout-method/', DoctorPayoutMethodView.as_view(), name='doctor-payout-method'),
    path('doctor/payout-method/generate-link/', GenerateStripeLinkView.as_view(), name='doctor-payout-generate-link'),
    path('doctor/payout-method/verify/', VerifyStripeAccountView.as_view(), name='doctor-payout-verify'),
    path('doctor/earnings-analytics/', DoctorEarningsAnalyticsView.as_view(), name='doctor-earnings-analytics'),
    path('doctor/wallet/withdraw/', RequestWithdrawalView.as_view(), name='doctor-withdraw'),

    # Documents
    path('documents/', DocumentUploadView.as_view(), name='documents'),
    path('documents/<int:pk>/delete/', DocumentDeleteView.as_view(), name='document-delete'),

    # Admin Users CRUD
    path('admin/users/', AdminUserManagementView.as_view(), name='admin-users'),
    path('admin/users/<int:pk>/', AdminUserDetailView.as_view(), name='admin-user-detail'),
    path('admin/overview/', AdminOverviewView.as_view(), name='admin-overview'),
    path('admin/appointments/<int:pk>/', AdminAppointmentManagementView.as_view(), name='admin-appointment-management'),
    path('admin/payments/<int:pk>/decision/', AdminPaymentDecisionView.as_view(), name='admin-payment-decision'),
    path('admin/comments/<int:pk>/', AdminChatMessageManagementView.as_view(), name='admin-comment-management'),
]
