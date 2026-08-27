from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

class User(AbstractUser):
    email = models.EmailField(unique=True)
    profile_pic = models.ImageField(upload_to="profile_image/", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    avatar_url = models.CharField(max_length=500, blank=True, null=True)
    subscription_status = models.BooleanField(default=False)
    mobile_number = models.CharField(max_length=15, blank=True, null=True)
    gender = models.CharField(max_length=10, blank=True, null=True)
    birthday = models.DateField(blank=True, null=True)
    
    USER_TYPE_CHOICES = (
        ('patient', 'Patient'),
        ('doctor', 'Doctor'),
    )
    user_type = models.CharField(
        max_length=10, 
        choices=USER_TYPE_CHOICES, 
        default='patient'
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def __str__(self):
        return self.email


class OTPCode(models.Model):
    code = models.CharField(max_length=6, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    expiration_time = models.DateTimeField()
    otp_status = models.BooleanField(default=False)

    def is_expired(self):
        return self.expiration_time < timezone.now()

    def is_Used(self):
        return self.otp_status
    
class Doctor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    specialization = models.CharField(max_length=500, blank=True, null=True)
    license_number = models.CharField(max_length=50, blank=True, null=True)
    hospital = models.CharField(max_length=200, blank=True, null=True)
    experience_years = models.FloatField(default=0)
    consultation_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    license_front_image = models.ImageField(upload_to="licenses/", null=True, blank=True)
    license_back_image = models.ImageField(upload_to="licenses/", null=True, blank=True)
    # ✅ NEW: Weekly Availability (JSON structure: {"Monday": {"start": "09:00", "end": "17:00", "active": true}, ...})
    availability = models.JSONField(default=dict, blank=True, null=True)
    
    def __str__(self):
        return f"Dr. {self.user.first_name} {self.user.last_name}"
    
class Patient(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    blood_group = models.CharField(max_length=5, blank=True, null=True)
    height = models.FloatField(blank=True, null=True)  # in cm
    weight = models.FloatField(blank=True, null=True)  # in kg
    
    def __str__(self):
        return f"Patient: {self.user.first_name} {self.user.last_name}"

class Appointment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
    ]
    PAYMENT_STATUS_CHOICES = [
        ('unpaid', 'Unpaid'),
        ('pending', 'Pending Admin Approval'),
        ('paid', 'Paid'),
        ('rejected', 'Rejected'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='appointments')
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='appointments')
    date_time = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='unpaid')
    payment_id = models.CharField(max_length=255, blank=True, null=True) 

    symptoms = models.TextField(blank=True, null=True)
    clinical_notes = models.TextField(blank=True, null=True)
    prescription = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Appt: {self.patient.user.first_name} with {self.doctor.user.first_name} - {self.status}"
    
class ChatMessage(models.Model):
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, related_name="messages")
    sender_type = models.CharField(max_length=10) 
    
    # Made text nullable so users can send just an image without typing text
    text = models.TextField(blank=True, null=True) 
    
    # Attachment field for sharing files/images in chat
    attachment = models.FileField(upload_to='chat_files/', null=True, blank=True)
    
    time = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender_type}: {self.text[:20] if self.text else 'Attachment'}"

class Document(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='documents')
    file = models.FileField(upload_to='patient_documents/')
    filename = models.CharField(max_length=255)
    file_size = models.IntegerField()
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.filename


class WithdrawalRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
    ]

    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='withdrawal_requests')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    requested_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Withdrawal {self.amount} by Dr. {self.doctor.user.first_name} — {self.status}"


class DoctorPayoutMethod(models.Model):
    doctor = models.OneToOneField(Doctor, on_delete=models.CASCADE, related_name='payout_method')
    stripe_account_id = models.CharField(max_length=255, blank=True, null=True)
    charges_enabled = models.BooleanField(default=False)
    details_submitted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payout Method for Dr. {self.doctor.user.first_name} ({self.stripe_account_id or 'Not Connected'})"