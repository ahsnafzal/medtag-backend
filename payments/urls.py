from django.urls import path

from . import views

app_name = 'payments'

urlpatterns = [
    path('jazzcash/start/<str:token>/', views.jazzcash_pay_start, name='jazzcash_start'),
    path('jazzcash/return/', views.jazzcash_pay_return, name='jazzcash_return'),
]
