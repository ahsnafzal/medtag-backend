from django.core.mail import EmailMessage
from django.conf import settings
import random
import string
from datetime import datetime, timedelta
from django.utils import timezone

class EmailService:
    @staticmethod
    def generate_otp():
        """Generate a 6-digit OTP"""
        return ''.join(random.choices(string.digits, k=6))
    
    @staticmethod
    def send_otp_email(user_email, user_name, otp_code):
        """Send OTP email to user"""
        subject = 'Verify Your Email - MedTag OTP Code'
        
        message = f"""
        Hello {user_name},
        
        Your OTP for email verification is: 
        
        🔐 **{otp_code}**
        
        This OTP will expire in 10 minutes.
        
        If you didn't request this, please ignore this email.
        
        Best regards,
        MedTag Team
        """
        
        try:
            email = EmailMessage(
                subject=subject,
                body=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user_email],
            )
            email.send()
            print(f"OTP email sent to {user_email}")
            return True
        except Exception as e:
            print(f"Failed to send email to {user_email}: {e}")
            return False
    
    @staticmethod
    def send_welcome_email(user_email, user_name):
        """Send welcome email after verification"""
        subject = 'Welcome to MedTag!'
        
        message = f"""
        Hello {user_name},
        
        🎉 Welcome to MedTag! Your account has been successfully verified.
        
        You can now login and access all features:
        - Track your medical history
        - Connect with doctors
        - Manage your health records
        
        Login here: http://localhost:3000/login
        
        Best regards,
        MedTag Team
        """
        
        try:
            email = EmailMessage(
                subject=subject,
                body=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user_email],
            )
            email.send()
            return True
        except Exception as e:
            print(f"Failed to send welcome email: {e}")
            return False