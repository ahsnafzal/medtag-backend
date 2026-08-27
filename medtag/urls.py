from django.urls import path
from .views import *
from . import views
from .views import get_booked_slots, get_server_ip


urlpatterns = [
        path('upload/', FileUploadAPIView.as_view(), name='file-upload'),
        path('upload/<int:pk>/', FileUploadAPIView.as_view(), name='file-delete'),

        path('reviews/create/', ReviewCreateView.as_view(), name='review-create'),
        path('reviews/', DoctorReviewListView.as_view(), name='review-list'),
        path('appointments/booked-slots/', views.get_booked_slots, name='booked-slots'),

        # ✅ Returns the server's real LAN IP for mobile-friendly QR codes
        path('server-ip/', get_server_ip, name='server-ip'),
]
