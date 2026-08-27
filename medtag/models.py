from django.db import models

from accounts.models import User

from accounts.models import User,Appointment, Doctor, Patient

class UserDocument(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    filename = models.CharField(max_length=255)
    document = models.FileField(upload_to='documents/')  # Local storage
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):

        return f"{self.user.username} - {self.filename}"

        return f"{self.user.username} - {self.filename}"
    
class Review(models.Model):
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, related_name='reviews')
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    rating = models.IntegerField()
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Review for Dr. {self.doctor.user.first_name} by {self.patient.user.first_name}"

