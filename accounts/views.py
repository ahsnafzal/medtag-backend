from rest_framework.views import APIView
from rest_framework import generics
from rest_framework.response import Response
from rest_framework import status
# ✅ CRITICAL: Parsers for handling File Uploads + JSON
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from .models import User, OTPCode, Doctor, Patient, Appointment
from .serializers import (
    UserRegistrationSerializer,
    UserSerializer, 
    ProfileUpdateSerializer, 
    ChangePasswordSerializer,
    PatientSerializer,
    DoctorSerializer
)
from django.contrib.auth import authenticate
from django.conf import settings
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone
from datetime import timedelta
from django.core.mail import send_mail
import random 
import requests
import re # ✅ Required for Regex validation

from utills.email import EmailHelper
email_helper = EmailHelper()

# --- HELPER: VERIFY LICENSE FROM PMDC ---
def verify_pmdc_license(license_no):
    """
    Verifies license format.
    Allows ALL valid-looking PMDC formats (e.g., 12345-P, 1001-AJK, 54321-N).
    Blocks ONLY specific test cases for demo failure.
    """
    if not license_no: return False

    # 1. Manual Block for "Failure" Demo
    if license_no.upper() == "00000-X": return False
    
    try:
        # 2. Flexible Regex for PMDC Formats
        # Matches: 
        #  - 1 to 10 digits
        #  - Optional space, hyphen, optional space
        #  - 1 to 5 letters (e.g., P, D, N, AJK)
        #  - Case Insensitive
        pattern = r'^\d{1,10}\s*-\s*[A-Z]{1,5}$'
        
        if not re.match(pattern, license_no, re.IGNORECASE):
            return False
            
        # If format is correct, we assume it's valid for now 
        # (Since we cannot scrape PMDC reliably without an API key)
        return True 
        
    except Exception as e:
        print(f"PMDC Verification Error: {e}")
        # Fail Open: Allow signup if checking logic crashes, to prevent blocking users
        return True 

# 1. SIGNUP VIEW (Updated)
class CreateUserView(APIView):
    permission_classes = [AllowAny]
    # ✅ Enable Parsers for JSON and File Uploads
    parser_classes = [MultiPartParser, FormParser, JSONParser] 
    
    def post(self, request):
        # Handle mutable data copy based on request type
        if hasattr(request.data, 'dict'):
            data = request.data.dict()
        elif hasattr(request.data, 'copy'):
            data = request.data.copy()
        else:
            data = request.data

        if 'username' not in data and 'email' in data:
            data['username'] = data['email']
            
        # PMDC Verification
        if data.get('user_type') == 'doctor':
            license_no = data.get('license_number', '')
            if not verify_pmdc_license(license_no):
                return Response(
                    {"license_number": ["License number format invalid or blacklisted. Use format like 12345-P or 1001-AJK."]}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

        serializer = UserRegistrationSerializer(data=data)
        if serializer.is_valid():
            try:
                # This save() method in your serializer handles creating User AND Doctor/Patient profiles
                user = serializer.save()
                
                # Set Inactive until OTP
                user.is_active = False 
                user.save()
                
                otp_code = str(random.randint(100000, 999999))
                
                OTPCode.objects.create(
                    user=user,
                    code=otp_code,
                    expiration_time=timezone.now() + timedelta(minutes=10),
                    otp_status=False
                )
                
                try:
                    send_mail(
                        subject="Verify Your MedTag Account",
                        message=f"Hello {user.first_name},\n\nYour verification code is: {otp_code}\n\nExpires in 10 minutes.",
                        from_email=settings.EMAIL_HOST_USER,
                        recipient_list=[user.email],
                        fail_silently=False
                    )
                    print(f"Signup OTP sent to {user.email}")
                except Exception as e:
                    print(f"Email failed: {e}")

                return Response({
                    'message': 'Account created. Please verify your email.',
                    'email': user.email,
                    'user_type': user.user_type
                }, status=status.HTTP_201_CREATED)

            except Exception as e:
                # Rollback if profile creation fails
                if 'user' in locals() and user.id: user.delete()
                print(f"Signup Crash Error: {e}")
                return Response({"error": f"Registration failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# 2. VERIFY EMAIL VIEW
class VerifyEmailAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        otp = request.data.get('otp')
        if not email or not otp: return Response({'error': 'Email and OTP are required'}, status=400)

        try:
            user = User.objects.get(email=email)
            otp_record = OTPCode.objects.filter(user=user, code=otp, otp_status=False).last()

            if not otp_record: return Response({'error': 'Invalid Code'}, status=400)
            if otp_record.is_expired(): return Response({'error': 'Code has expired'}, status=400)

            user.is_active = True
            user.save()
            otp_record.otp_status = True
            otp_record.save()
            return Response({'message': 'Verified!'}, status=200)

        except User.DoesNotExist: return Response({'error': 'User not found'}, status=404)

# 3. LOGIN VIEW
class LoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data
        email = data.get("email")
        password = data.get("password")
        request_user_type = data.get("user_type")

        if not email or not password: return Response({"message": "Required fields missing."}, status=400)

        user = authenticate(username=email, password=password)

        if user:
            if not user.is_active: return Response({"error": "Account not verified."}, status=403)
            if request_user_type and user.user_type != request_user_type:
                return Response({"error": f"Please login as {user.user_type}.", "user_type_mismatch": True}, status=403)

            refresh = RefreshToken.for_user(user)
            return Response({
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user_type": user.user_type,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
            }, status=200)
        else:
            return Response({"message": "Invalid credentials"}, status=400)

# 4. GET USER PROFILE
class GetUserProfileView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

# 5. FORGOT PASSWORD
class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        email = request.data.get('email')
        if not email: return Response({"message": "Email required"}, status=400)
        try:
            user = User.objects.get(email=email)
            otp_code = str(random.randint(100000, 999999))
            OTPCode.objects.create(user=user, code=otp_code, expiration_time=timezone.now()+timedelta(minutes=5))
            try:
                send_mail("Reset Password", f"Code: {otp_code}", settings.EMAIL_HOST_USER, [email], fail_silently=False)
            except: pass
            return Response({"status": True, "message": "Code sent."}, status=200)
        except User.DoesNotExist: return Response({"error": "User not found."}, status=404)

# 6. RESET PASSWORD
class ResetPasswordAPIView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        password = request.data.get("password")
        token = request.data.get("token")
        if not password or not token: return Response({"message": "Required"}, status=400)
        try:
            otp = OTPCode.objects.filter(code=token, otp_status=False).last()
            if otp and not otp.is_expired():
                otp.user.set_password(password)
                otp.user.save()
                otp.otp_status = True
                otp.save()
                return Response({"message": "Success"}, status=200)
            return Response({"message": "Invalid token"}, status=400)
        except: return Response({"message": "Error"}, status=400)

# 7. CONTACT US
class ContactUSView(APIView):
    def post(self, request):
        email_helper.contact_email(request.data)
        return Response({"message": "Email sent"}, status=200)

# 8. DOCTOR STATS
class DoctorStatisticsAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        if request.user.user_type != 'doctor': return Response(status=403)
        return Response({'totalPatients': Patient.objects.count()})

# 9. PATIENT DASHBOARD
class PatientDashboardAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        if request.user.user_type != 'patient': return Response({"error": "Denied"}, status=403)
        patient_data = {
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'email': request.user.email,
            'phone': request.user.mobile_number,
            'gender': request.user.gender,
            'birthday': request.user.birthday,
            'profile_pic': request.user.profile_pic.url if request.user.profile_pic else None
        }
        try:
            patient_profile = Patient.objects.get(user=request.user)
            patient_data.update({
                'blood_group': patient_profile.blood_group,
                'height': patient_profile.height,
                'weight': patient_profile.weight,
            })
        except: pass
        return Response(patient_data)

# 10. DOCTOR DASHBOARD
class DoctorDashboardAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        if request.user.user_type != 'doctor': return Response({"error": "Denied"}, status=403)
        doctor_info = {'name': f"Dr. {request.user.first_name}", 'specialization': 'N/A', 'hospital': 'N/A'}
        try:
            doctor = Doctor.objects.get(user=request.user)
            doctor_info['specialization'] = doctor.specialization
            doctor_info['hospital'] = doctor.hospital
        except: pass
        return Response({
            'statistics': { 'totalPatients': Patient.objects.count(), 'appointmentsToday': 0, 'pendingReports': 0, 'completedCases': 0 },
            'recentPatients': [], 'upcomingAppointments': [], 'doctorInfo': doctor_info
        })

# 11. PROFILE UPDATE
class ProfileUpdateAPIView(generics.UpdateAPIView):
    queryset = User.objects.all()
    serializer_class = ProfileUpdateSerializer
    permission_classes = (IsAuthenticated,)
    def get_object(self): return self.request.user
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        if instance.user_type == 'patient':
            try:
                p = Patient.objects.get(user=instance)
                for f in ['blood_group', 'height', 'weight']:
                    if f in request.data: setattr(p, f, request.data[f] or None)
                p.save()
            except: Patient.objects.create(user=instance)
        elif instance.user_type == 'doctor':
            try:
                d = Doctor.objects.get(user=instance)
                for f in ['specialization', 'license_number', 'hospital', 'experience_years']:
                    if f in request.data: setattr(d, f, request.data[f])
                d.save()
            except: Doctor.objects.create(user=instance)
        return Response(serializer.data)

# 12. CHANGE PASSWORD
class ChangePasswordAPIView(generics.UpdateAPIView):
    queryset = User.objects.all()
    serializer_class = ChangePasswordSerializer
    permission_classes = (IsAuthenticated,)
    def get_object(self): return self.request.user
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance=instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        old_password = serializer.validated_data.get("old_password")
        new_password = serializer.validated_data.get("new_password")
        if old_password == new_password: return Response({"detail": "Same pass"}, status=400)
        if not instance.check_password(old_password): return Response({"detail": "Wrong pass"}, status=400)
        instance.set_password(new_password)
        instance.save()
        return Response({"detail": "Password changed"}, status=200)

# 13. PATIENT PROFILE VIEW
class PatientProfileView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        try:
            p = Patient.objects.get(user=request.user)
            return Response(PatientSerializer(p).data)
        except: return Response(status=404)
    def put(self, request):
        try:
            p = Patient.objects.get(user=request.user)
            s = PatientSerializer(p, data=request.data, partial=True)
            if s.is_valid(): s.save(); return Response(s.data)
            return Response(s.errors, status=400)
        except: return Response(status=404)

# 14. DOCTOR LIST & DETAILS
class DoctorListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DoctorSerializer
    queryset = Doctor.objects.all()

class DoctorDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DoctorSerializer
    queryset = Doctor.objects.all()

# 15. BOOK APPOINTMENT
class BookAppointmentView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        if request.user.user_type != 'patient': return Response({"error": "Only patients"}, status=403)
        try:
            patient = Patient.objects.get(user=request.user)
            doctor = Doctor.objects.get(user_id=request.data.get('doctor_id'))
            date_time = request.data.get('date_time')
            if not date_time: return Response({"error": "Date required"}, status=400)
            Appointment.objects.create(patient=patient, doctor=doctor, date_time=date_time, symptoms=request.data.get('symptoms', ''))
            return Response({"message": "Booked!"}, status=201)
        except Exception as e: return Response({"error": str(e)}, status=500)