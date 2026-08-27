import stripe
import random 
import re 

from rest_framework.views import APIView
from rest_framework import generics
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404
from django.db import transaction
from datetime import timedelta, datetime
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models import User, OTPCode, Doctor, Patient, Appointment, ChatMessage, Document, WithdrawalRequest, DoctorPayoutMethod
from .call_session import reserve_call_slot, release_call_slot
from .serializers import (
    UserRegistrationSerializer,
    UserSerializer, 
    ProfileUpdateSerializer, 
    ChangePasswordSerializer,
    PatientSerializer,
    DoctorSerializer,
    AppointmentSerializer,
    DocumentSerializer,
    AdminManagedUserSerializer
)
from utills.email import EmailHelper

email_helper = EmailHelper()

# ✅ STRIPE SECRET KEY
stripe.api_key = settings.STRIPE_SECRET_KEY


def send_realtime_notification(user_id, payload):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    async_to_sync(channel_layer.group_send)(
        f"notifications_{user_id}",
        {
            "type": "notification_message",
            "message": payload,
        },
    )


def _is_slot_conflict(doctor, when, exclude_appointment_id=None):
    qs = Appointment.objects.filter(doctor=doctor, date_time=when).exclude(status='cancelled').exclude(payment_status='rejected')
    if exclude_appointment_id:
        qs = qs.exclude(id=exclude_appointment_id)
    return qs.exists()


def _attempt_refund_for_appointment(appointment):
    """
    Refund patient when there is a captured/processing Stripe payment for this appointment.
    Returns: (refunded: bool, refund_id_or_none: str|None, note: str)
    """
    if not appointment.payment_id:
        return False, None, "No payment intent found."
    if appointment.payment_status not in ['pending', 'paid']:
        return False, None, "Appointment is not in a refundable payment state."

    try:
        intent = stripe.PaymentIntent.retrieve(appointment.payment_id)
        status_value = getattr(intent, "status", "")
        if status_value not in ['succeeded', 'processing', 'requires_capture']:
            return False, None, f"Payment intent status '{status_value}' is not refundable."

        refund = stripe.Refund.create(
            payment_intent=appointment.payment_id,
            reason='requested_by_customer',
            reverse_transfer=True,
        )
        return True, getattr(refund, "id", None), "Refund submitted to Stripe."
    except Exception as exc:
        return False, None, f"Refund failed: {str(exc)}"

# --- HELPER: VERIFY LICENSE FROM PMDC ---
def verify_pmdc_license(license_no):
    if not license_no: return False
    if license_no.upper() == "00000-X": return False
    try:
        pattern = r'^\d{1,10}\s*-\s*[A-Z]{1,5}$'
        if not re.match(pattern, license_no, re.IGNORECASE):
            return False
        return True 
    except Exception as e:
        print(f"PMDC Verification Error: {e}")
        return True 
    blocked = ["00000-X", "00000", "123", "TEST"]
    if license_no.upper() in blocked: return False
    if len(license_no.strip()) >= 3: return True
    return False


# 1. SIGNUP VIEW
class CreateUserView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser, JSONParser] 
    
    def post(self, request):
        if hasattr(request.data, 'dict'):
            data = request.data.dict()
        elif hasattr(request.data, 'copy'):
            data = request.data.copy()
        else:
            data = request.data

        if 'username' not in data and 'email' in data:
            data['username'] = data['email']
            
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
                user = serializer.save()
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
                except Exception as e:
                    print(f"Email failed: {e}")

                return Response({
                    'message': 'Account created. Please verify your email.',
                    'email': user.email,
                    'user_type': user.user_type
                }, status=status.HTTP_201_CREATED)

            except Exception as e:
                if 'user' in locals() and user.id: user.delete()
                return Response({"error": f"Registration failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# 2. VERIFY EMAIL VIEW
class VerifyEmailAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        otp = request.data.get('otp')
        
        if not email or not otp: 
            return Response({'error': 'Email and OTP are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
            otp_record = OTPCode.objects.filter(user=user, code=otp, otp_status=False).last()

            if not otp_record: 
                return Response({'error': 'Invalid Code'}, status=status.HTTP_400_BAD_REQUEST)
            if otp_record.is_expired(): 
                return Response({'error': 'Code has expired'}, status=status.HTTP_400_BAD_REQUEST)

            user.is_active = True
            user.save()
            
            otp_record.otp_status = True
            otp_record.save()
            
            return Response({'message': 'Verified!'}, status=status.HTTP_200_OK)

        except User.DoesNotExist: 
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)


# 3. LOGIN VIEW
class LoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data
        email = data.get("email")
        password = data.get("password")
        request_user_type = data.get("user_type")

        if not email or not password: 
            return Response({"message": "Required fields missing."}, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(username=email, password=password)

        if user:
            if not user.is_active: 
                return Response({"error": "Account not verified."}, status=status.HTTP_403_FORBIDDEN)
            role = "admin" if (user.is_staff or user.is_superuser) else user.user_type
            if request_user_type and role != request_user_type:
                return Response({"error": f"Please login as {role}.", "user_type_mismatch": True}, status=status.HTTP_403_FORBIDDEN)

            refresh = RefreshToken.for_user(user)
            return Response({
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user_type": user.user_type,
                "role": role,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
            }, status=status.HTTP_200_OK)
        else:
            return Response({"message": "Invalid credentials"}, status=status.HTTP_400_BAD_REQUEST)


# 4. GET USER PROFILE
class GetUserProfileView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)


class AdminUserManagementView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        role_filter = request.query_params.get('role')
        users = User.objects.all().order_by('-created_at')

        if role_filter == 'doctor':
            users = users.filter(user_type='doctor')
        elif role_filter == 'patient':
            users = users.filter(user_type='patient')
        elif role_filter == 'admin':
            users = users.filter(is_staff=True)

        serializer = AdminManagedUserSerializer(users, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        data = request.data

        email = data.get('email')
        password = data.get('password')
        user_type = data.get('user_type', 'patient')

        if not email or not password:
            return Response({'error': 'email and password are required.'}, status=status.HTTP_400_BAD_REQUEST)
        if user_type not in ['patient', 'doctor', 'admin']:
            return Response({'error': 'user_type must be patient, doctor, or admin.'}, status=status.HTTP_400_BAD_REQUEST)
        if User.objects.filter(email=email).exists():
            return Response({'error': 'A user with this email already exists.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=data.get('username') or email,
                    email=email,
                    password=password,
                    first_name=data.get('first_name', ''),
                    last_name=data.get('last_name', ''),
                    mobile_number=data.get('mobile_number'),
                    gender=data.get('gender'),
                    birthday=data.get('birthday') or None,
                    user_type='doctor' if user_type == 'doctor' else 'patient',
                )

                user.is_active = bool(data.get('is_active', True))
                user.is_staff = user_type == 'admin' or bool(data.get('is_staff', False))
                user.is_superuser = bool(data.get('is_superuser', False))
                user.save()

                if user_type == 'doctor':
                    Doctor.objects.create(
                        user=user,
                        specialization=data.get('specialization', ''),
                        license_number=data.get('license_number', ''),
                        hospital=data.get('hospital', ''),
                        experience_years=data.get('experience_years') or 0,
                        consultation_fee=data.get('consultation_fee') or 0,
                        availability=data.get('availability') or {},
                    )
                elif user_type == 'patient':
                    Patient.objects.create(
                        user=user,
                        blood_group=data.get('blood_group'),
                        height=data.get('height') or None,
                        weight=data.get('weight') or None,
                    )

            return Response(
                {
                    'message': 'User created successfully.',
                    'user': AdminManagedUserSerializer(user).data
                },
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class AdminUserDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def put(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        data = request.data

        user_type = data.get('user_type', user.user_type)
        if user_type not in ['patient', 'doctor', 'admin']:
            return Response({'error': 'user_type must be patient, doctor, or admin.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                for field in ['first_name', 'last_name', 'mobile_number', 'gender', 'birthday']:
                    if field in data:
                        setattr(user, field, data.get(field) or None)

                if 'email' in data:
                    new_email = data.get('email')
                    if User.objects.exclude(pk=user.pk).filter(email=new_email).exists():
                        return Response({'error': 'A user with this email already exists.'}, status=status.HTTP_400_BAD_REQUEST)
                    user.email = new_email
                    user.username = data.get('username') or new_email

                if 'password' in data and data.get('password'):
                    user.set_password(data.get('password'))

                if user_type in ['patient', 'doctor']:
                    user.user_type = user_type
                    user.is_staff = bool(data.get('is_staff', user.is_staff))
                    user.is_superuser = bool(data.get('is_superuser', user.is_superuser))
                else:
                    user.user_type = 'patient'
                    user.is_staff = True
                    user.is_superuser = bool(data.get('is_superuser', user.is_superuser))

                if 'is_active' in data:
                    user.is_active = bool(data.get('is_active'))
                user.save()

                if user_type == 'doctor':
                    doctor, _ = Doctor.objects.get_or_create(user=user)
                    for field in ['specialization', 'license_number', 'hospital', 'experience_years', 'consultation_fee', 'availability']:
                        if field in data:
                            setattr(doctor, field, data.get(field) if data.get(field) is not None else getattr(doctor, field))
                    doctor.save()
                    Patient.objects.filter(user=user).delete()
                elif user_type == 'patient':
                    patient, _ = Patient.objects.get_or_create(user=user)
                    for field in ['blood_group', 'height', 'weight']:
                        if field in data:
                            setattr(patient, field, data.get(field) or None)
                    patient.save()
                    Doctor.objects.filter(user=user).delete()

            return Response(
                {
                    'message': 'User updated successfully.',
                    'user': AdminManagedUserSerializer(user).data
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        user = get_object_or_404(User, pk=pk)

        if request.user.pk == user.pk:
            return Response({'error': 'You cannot deactivate your own admin account.'}, status=status.HTTP_400_BAD_REQUEST)

        user.is_active = False
        user.save(update_fields=['is_active'])
        return Response({'message': 'User deactivated successfully.'}, status=status.HTTP_200_OK)


# 5. FORGOT PASSWORD
class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        email = request.data.get('email')
        if not email: return Response({"message": "Email required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user = User.objects.get(email=email)
            otp_code = str(random.randint(100000, 999999))
            OTPCode.objects.create(user=user, code=otp_code, expiration_time=timezone.now()+timedelta(minutes=5))
            try:
                send_mail("Reset Password", f"Code: {otp_code}", settings.EMAIL_HOST_USER, [email], fail_silently=False)
            except: pass
            return Response({"status": True, "message": "Code sent."}, status=status.HTTP_200_OK)
        except User.DoesNotExist: 
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)


# 6. RESET PASSWORD
class ResetPasswordAPIView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        password = request.data.get("password")
        token = request.data.get("token")
        if not password or not token: return Response({"message": "Required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            otp = OTPCode.objects.filter(code=token, otp_status=False).last()
            if otp and not otp.is_expired():
                otp.user.set_password(password)
                otp.user.save()
                otp.otp_status = True
                otp.save()
                return Response({"message": "Success"}, status=status.HTTP_200_OK)
            return Response({"message": "Invalid token"}, status=status.HTTP_400_BAD_REQUEST)
        except: 
            return Response({"message": "Error"}, status=status.HTTP_400_BAD_REQUEST)


# 7. CONTACT US
class ContactUSView(APIView):
    def post(self, request):
        email_helper.contact_email(request.data)
        return Response({"message": "Email sent"}, status=status.HTTP_200_OK)


# 8. DOCTOR STATS
class DoctorStatisticsAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        if request.user.user_type != 'doctor': return Response(status=status.HTTP_403_FORBIDDEN)
        return Response({'totalPatients': Patient.objects.count()})


# 9. PATIENT DASHBOARD
class PatientDashboardAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        if request.user.user_type != 'patient': return Response({"error": "Denied"}, status=status.HTTP_403_FORBIDDEN)
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
        if request.user.user_type != 'doctor': return Response(status=403)
        try:
            doctor = Doctor.objects.get(user=request.user)
            all_apts = Appointment.objects.filter(doctor=doctor).order_by('-date_time')
            pending = all_apts.filter(status='pending')
            # Show confirmed appointments immediately after payment submission as well
            # (pending = paid by patient, waiting admin decision).
            confirmed = all_apts.filter(status='confirmed', payment_status__in=['paid', 'pending'])
            completed = all_apts.filter(status='completed')
            
            patients_dict = {}
            for appt in completed:
                p_user = appt.patient.user
                if p_user.id not in patients_dict:
                    patients_dict[p_user.id] = {
                        'id': appt.id, 
                        'patient_id': p_user.id,
                        'first_name': p_user.first_name,
                        'last_name': p_user.last_name, 
                        'email': p_user.email,
                        'profile_pic': p_user.profile_pic.url if p_user.profile_pic else None,
                        'latest_appointment_id': appt.id 
                    }
            
            return Response({
                'statistics': { 
                    'totalPatients': len(patients_dict), 
                    'appointmentsToday': confirmed.filter(date_time__date=timezone.now().date()).count(), 
                    'pendingReports': pending.count(), 
                    'completedCases': completed.count() 
                },
                'notifications': AppointmentSerializer(pending, many=True).data,
                'upcomingAppointments': AppointmentSerializer(confirmed, many=True).data,
                'patients': list(patients_dict.values()), 
                'allAppointments': AppointmentSerializer(all_apts, many=True).data, # ✅ YEH LINE ADD KI HAI (Poori History ke liye)
                'doctorInfo': {'name': f"Dr. {request.user.first_name}", 'specialization': doctor.specialization}
            })
        except: return Response({"error": "Profile error"}, status=404)

# 11. PROFILE UPDATE
class ProfileUpdateAPIView(generics.UpdateAPIView):
    queryset = User.objects.all()
    serializer_class = ProfileUpdateSerializer
    permission_classes = (IsAuthenticated,)
    
    def get_object(self): 
        return self.request.user
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        if instance.user_type == 'patient':
            try:
                p = Patient.objects.get(user=instance)
            except Patient.DoesNotExist: 
                p = Patient.objects.create(user=instance)
                
            for f in ['blood_group', 'height', 'weight']:
                if f in request.data: 
                    val = request.data[f]
                    if f in ['height', 'weight'] and val == '':
                        val = None
                    setattr(p, f, val)
            p.save()
            
        elif instance.user_type == 'doctor':
            try:
                d = Doctor.objects.get(user=instance)
            except Doctor.DoesNotExist: 
                d = Doctor.objects.create(user=instance)
                
            for f in ['specialization', 'license_number', 'hospital', 'experience_years', 'consultation_fee', 'availability']:
                if f in request.data: 
                    val = request.data[f]
                    if f in ['experience_years', 'consultation_fee'] and val == '':
                        val = 0
                    setattr(d, f, val)
            d.save()
            
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
        if old_password == new_password: return Response({"detail": "Same pass"}, status=status.HTTP_400_BAD_REQUEST)
        if not instance.check_password(old_password): return Response({"detail": "Wrong pass"}, status=status.HTTP_400_BAD_REQUEST)
        instance.set_password(new_password)
        instance.save()
        return Response({"detail": "Password changed"}, status=status.HTTP_200_OK)


# 13. PATIENT PROFILE VIEW
class PatientProfileView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            p = Patient.objects.get(user=request.user)
            return Response(PatientSerializer(p).data)
        except: return Response(status=status.HTTP_404_NOT_FOUND)
        
    def put(self, request):
        try:
            p = Patient.objects.get(user=request.user)
            s = PatientSerializer(p, data=request.data, partial=True)
            if s.is_valid(): 
                s.save()
                return Response(s.data)
            return Response(s.errors, status=status.HTTP_400_BAD_REQUEST)
        except: return Response(status=status.HTTP_404_NOT_FOUND)


# 14. DOCTOR LIST & DETAILS
class DoctorListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DoctorSerializer
    queryset = Doctor.objects.all()


class DoctorDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DoctorSerializer
    queryset = Doctor.objects.all()


class BookedSlotsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        doctor_id = request.query_params.get('doctor_id')
        date_raw = request.query_params.get('date')
        exclude_appointment_id = request.query_params.get('exclude_appointment_id')

        if not doctor_id or not date_raw:
            return Response({"error": "doctor_id and date are required."}, status=status.HTTP_400_BAD_REQUEST)

        target_date = parse_date(date_raw)
        if not target_date:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            doctor = Doctor.objects.get(user__id=int(doctor_id))
        except (ValueError, Doctor.DoesNotExist):
            return Response({"error": "Doctor not found."}, status=status.HTTP_404_NOT_FOUND)

        appointments = Appointment.objects.filter(
            doctor=doctor,
            date_time__date=target_date
        ).exclude(status='cancelled').exclude(payment_status='rejected').order_by('date_time')

        if exclude_appointment_id:
            try:
                appointments = appointments.exclude(id=int(exclude_appointment_id))
            except ValueError:
                pass

        booked_slots = [apt.date_time.strftime("%H:%M") for apt in appointments]
        return Response({"booked_slots": booked_slots}, status=status.HTTP_200_OK)


# 15. BOOK APPOINTMENT
class BookAppointmentView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        if request.user.user_type != 'patient': 
            return Response({"error": "Only patients can book appointments."}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            patient = Patient.objects.get(user=request.user)
            doctor_id = request.data.get('doctor_id')
            if not doctor_id:
                return Response({"error": "doctor_id is required."}, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                doctor = Doctor.objects.get(user__id=int(doctor_id))
            except ValueError:
                return Response({"error": "Invalid doctor_id."}, status=status.HTTP_400_BAD_REQUEST)
            except Doctor.DoesNotExist:
                return Response({"error": "Doctor not found."}, status=status.HTTP_404_NOT_FOUND)
                
            date_time = request.data.get('date_time')
            if not date_time: 
                return Response({"error": "Date and time are required."}, status=status.HTTP_400_BAD_REQUEST)

            try:
                parsed_dt = datetime.fromisoformat(str(date_time).replace("Z", "+00:00"))
                if timezone.is_naive(parsed_dt):
                    parsed_dt = timezone.make_aware(parsed_dt, timezone.get_current_timezone())
            except Exception:
                return Response({"error": "Invalid date_time format."}, status=status.HTTP_400_BAD_REQUEST)

            if _is_slot_conflict(doctor, parsed_dt):
                return Response(
                    {"error": "This slot is already booked. Please select another time."},
                    status=status.HTTP_409_CONFLICT
                )
            
            appointment = Appointment.objects.create(
                patient=patient, 
                doctor=doctor, 
                date_time=parsed_dt, 
                symptoms=request.data.get('symptoms', ''),
                status='pending',
                payment_status='unpaid'
            )

            send_realtime_notification(
                doctor.user.id,
                {
                    "type": "appointment_request",
                    "appointment_id": appointment.id,
                    "patient_name": f"{patient.user.first_name} {patient.user.last_name}".strip(),
                    "date_time": str(appointment.date_time),
                    "message": "New appointment request received.",
                }
            )
            
            return Response({
                "message": "Appointment request sent successfully!",
                "appointment_id": appointment.id
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e: 
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# 16. DOCTOR APPROVE/REJECT APPOINTMENT
class UpdateAppointmentStatusView(APIView):
    permission_classes = [IsAuthenticated]
    
    def put(self, request, pk):
        if request.user.user_type != 'doctor':
            return Response({"error": "Only doctors can update status."}, status=status.HTTP_403_FORBIDDEN)
            
        try:
            doctor = Doctor.objects.get(user=request.user)
            appointment = Appointment.objects.get(id=pk, doctor=doctor)
            
            new_status = request.data.get('status')
            if new_status not in ['confirmed', 'cancelled', 'completed']:
                return Response({"error": "Invalid status."}, status=status.HTTP_400_BAD_REQUEST)
                
            appointment.status = new_status
            appointment.save()

            send_realtime_notification(
                appointment.patient.user.id,
                {
                    "type": "appointment_status",
                    "appointment_id": appointment.id,
                    "status": appointment.status,
                    "doctor_name": f"{doctor.user.first_name} {doctor.user.last_name}".strip(),
                    "message": f"Doctor updated your appointment status to {appointment.status}.",
                }
            )
            
            return Response({"message": f"Appointment {new_status} successfully!"}, status=status.HTTP_200_OK)
            
        except Appointment.DoesNotExist:
            return Response({"error": "Appointment not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# 16.5 CANCEL APPOINTMENT — both patient and doctor can cancel
class CancelAppointmentView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        try:
            cancelled_by = request.user.user_type
            if request.user.user_type == 'patient':
                patient = Patient.objects.get(user=request.user)
                appointment = Appointment.objects.get(id=pk, patient=patient)
            elif request.user.user_type == 'doctor':
                doctor = Doctor.objects.get(user=request.user)
                appointment = Appointment.objects.get(id=pk, doctor=doctor)
            else:
                return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

            if appointment.status == 'cancelled':
                return Response({"message": "Appointment already cancelled."}, status=status.HTTP_200_OK)

            refunded, refund_id, refund_note = _attempt_refund_for_appointment(appointment)

            appointment.status = 'cancelled'
            if refunded:
                appointment.payment_status = 'rejected'
            appointment.save()

            by_label = "doctor" if cancelled_by == 'doctor' else "patient"
            send_realtime_notification(
                appointment.patient.user.id,
                {
                    "type": "appointment_cancelled",
                    "appointment_id": appointment.id,
                    "cancelled_by": by_label,
                    "message": f"Appointment was cancelled by {by_label}.",
                }
            )
            send_realtime_notification(
                appointment.doctor.user.id,
                {
                    "type": "appointment_cancelled",
                    "appointment_id": appointment.id,
                    "cancelled_by": by_label,
                    "message": f"Appointment was cancelled by {by_label}.",
                }
            )

            if refunded:
                refund_message_patient = "Your payment has been refunded."
                if refund_id:
                    refund_message_patient = f"Your payment has been refunded. Refund ID: {refund_id}"
                send_realtime_notification(
                    appointment.patient.user.id,
                    {
                        "type": "payment_refund",
                        "appointment_id": appointment.id,
                        "refund_id": refund_id,
                        "message": refund_message_patient,
                    }
                )
                send_realtime_notification(
                    appointment.doctor.user.id,
                    {
                        "type": "payment_refund",
                        "appointment_id": appointment.id,
                        "refund_id": refund_id,
                        "message": "Payment for cancelled appointment was refunded to patient.",
                    }
                )

            return Response(
                {
                    "message": "Appointment cancelled successfully!",
                    "refund_processed": refunded,
                    "refund_id": refund_id,
                    "refund_note": refund_note,
                },
                status=status.HTTP_200_OK
            )

        except (Patient.DoesNotExist, Doctor.DoesNotExist):
            return Response({"error": "Profile not found."}, status=status.HTTP_404_NOT_FOUND)
        except Appointment.DoesNotExist:
            return Response({"error": "Appointment not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# 16.6 RESCHEDULE APPOINTMENT — both patient and doctor can reschedule
class RescheduleAppointmentView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        new_date_time = request.data.get('new_date_time')
        if not new_date_time:
            return Response({"error": "new_date_time is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            requester_role = request.user.user_type
            if request.user.user_type == 'patient':
                patient = Patient.objects.get(user=request.user)
                appointment = Appointment.objects.get(id=pk, patient=patient)
            elif request.user.user_type == 'doctor':
                doctor = Doctor.objects.get(user=request.user)
                appointment = Appointment.objects.get(id=pk, doctor=doctor)
            else:
                return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

            try:
                parsed_dt = datetime.fromisoformat(str(new_date_time).replace("Z", "+00:00"))
                if timezone.is_naive(parsed_dt):
                    parsed_dt = timezone.make_aware(parsed_dt, timezone.get_current_timezone())
            except Exception:
                return Response({"error": "Invalid new_date_time format."}, status=status.HTTP_400_BAD_REQUEST)

            if _is_slot_conflict(appointment.doctor, parsed_dt, exclude_appointment_id=appointment.id):
                return Response({"error": "Requested slot is already booked."}, status=status.HTTP_409_CONFLICT)

            appointment.date_time = parsed_dt
            appointment.status = 'pending'   # Reset so doctor re-confirms
            appointment.save()

            send_realtime_notification(
                appointment.patient.user.id,
                {
                    "type": "appointment_rescheduled",
                    "appointment_id": appointment.id,
                    "message": f"Appointment rescheduled by {requester_role}. Waiting doctor confirmation.",
                    "date_time": str(appointment.date_time),
                }
            )
            send_realtime_notification(
                appointment.doctor.user.id,
                {
                    "type": "appointment_rescheduled",
                    "appointment_id": appointment.id,
                    "message": f"Appointment rescheduled by {requester_role}. Waiting doctor confirmation.",
                    "date_time": str(appointment.date_time),
                }
            )
            return Response({"message": "Appointment rescheduled successfully!"}, status=status.HTTP_200_OK)

        except (Patient.DoesNotExist, Doctor.DoesNotExist):
            return Response({"error": "Profile not found."}, status=status.HTTP_404_NOT_FOUND)
        except Appointment.DoesNotExist:
            return Response({"error": "Appointment not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UpdateAppointmentRecordView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            appointment = Appointment.objects.get(id=pk)
            # Check permissions
            if request.user.user_type == 'doctor':
                doctor = Doctor.objects.get(user=request.user)
                if appointment.doctor != doctor:
                    return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
            elif request.user.user_type == 'patient':
                patient = Patient.objects.get(user=request.user)
                if appointment.patient != patient:
                    return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
            else:
                return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

            return Response({
                "clinical_notes": appointment.clinical_notes,
                "prescription": appointment.prescription
            }, status=status.HTTP_200_OK)

        except Appointment.DoesNotExist:
            return Response({"error": "Appointment not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def put(self, request, pk):
        if request.user.user_type != 'doctor':
            return Response({"error": "Only doctors can update records."}, status=status.HTTP_403_FORBIDDEN)

        try:
            doctor = Doctor.objects.get(user=request.user)
            appointment = Appointment.objects.get(id=pk, doctor=doctor)

            appointment.clinical_notes = request.data.get('clinical_notes', appointment.clinical_notes)
            appointment.prescription = request.data.get('prescription', appointment.prescription)
            appointment.save()

            return Response({"message": "Records updated successfully!"}, status=status.HTTP_200_OK)

        except (Doctor.DoesNotExist, Appointment.DoesNotExist):
            return Response({"error": "Appointment or Profile not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



# 17. PATIENT APPOINTMENTS LIST
class PatientAppointmentsView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        if request.user.user_type != 'patient': 
            return Response({"error": "Only patients"}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            patient = Patient.objects.get(user=request.user)
            # Use select_related to fetch doctor and patient user data in one query
            appointments = Appointment.objects.filter(patient=patient).select_related(
                'doctor', 'doctor__user', 'patient', 'patient__user'
            ).order_by('-date_time')
            data = AppointmentSerializer(appointments, many=True).data
            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# 18. PROCESS PAYMENT (REAL STRIPE INTENT)
class ProcessPaymentView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        if request.user.user_type != 'patient': 
            return Response({"error": "Only patients can pay"}, status=status.HTTP_403_FORBIDDEN)
            
        try:
            patient = Patient.objects.get(user=request.user)
            appointment = Appointment.objects.get(id=pk, patient=patient)
            
            fee_value = appointment.doctor.consultation_fee
            doctor_fee = float(fee_value) if fee_value else 0

            intent_for = (request.data.get('intent_for') or '').strip().lower() or 'card'
            
            # Wallet sandbox: return amount only (no Stripe PI) so JazzCash/EasyPaisa can be tested locally.
            if intent_for == 'wallet':
                if not getattr(settings, 'WALLET_PAYMENT_SANDBOX', False):
                    return Response(
                        {"error": "Mobile wallet sandbox is disabled. Enable WALLET_PAYMENT_SANDBOX to test."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if doctor_fee < 0.50:
                    return Response({
                        "error": f"Doctor's fee (${doctor_fee}) is too low. Minimum amount must be at least $0.50."
                    }, status=status.HTTP_400_BAD_REQUEST)
                return Response({
                    "amount": doctor_fee,
                    "wallet_mode": True,
                }, status=status.HTTP_200_OK)

            if doctor_fee < 0.50:
                return Response({
                    "error": f"Doctor's fee (${doctor_fee}) is too low. Minimum amount must be at least $0.50 for Stripe."
                }, status=status.HTTP_400_BAD_REQUEST)
            
            amount_in_cents = int(doctor_fee * 100)

            doctor_payout = DoctorPayoutMethod.objects.filter(doctor=appointment.doctor).first()
            if not doctor_payout or not doctor_payout.stripe_account_id:
                return Response({"error": "Doctor payout account is not connected to Stripe."}, status=status.HTTP_400_BAD_REQUEST)

            intent = stripe.PaymentIntent.create(
                amount=amount_in_cents,
                currency='usd',
                payment_method_types=['card'],
                metadata={'appointment_id': appointment.id, 'doctor_id': appointment.doctor.user.id},
                transfer_data={
                    'destination': doctor_payout.stripe_account_id,
                },
            )

            return Response({
                "client_secret": intent.client_secret,
                "amount": doctor_fee
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# 18.5 CONFIRM PAYMENT (AFTER STRIPE SUCCESS)
class ConfirmPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if request.user.user_type != 'patient':
            return Response({"error": "Only patients can confirm payment."}, status=status.HTTP_403_FORBIDDEN)

        try:
            print(f"\n=== ConfirmPaymentView START ===")
            print(f"User: {request.user.id}, Appointment ID: {pk}")
            print(f"Request data: {request.data}")
            
            patient = Patient.objects.get(user=request.user)
            appointment = get_object_or_404(Appointment, id=pk, patient=patient)
            print(f"Appointment found: {appointment.id}, Doctor: {appointment.doctor.user.id}")

            transaction_id = request.data.get('transaction_id')
            payment_method = str(request.data.get('method') or 'card').lower()

            if not transaction_id:
                return Response({"error": "Transaction ID is missing."}, status=status.HTTP_400_BAD_REQUEST)

            print(f"Transaction ID: {transaction_id}, Method: {payment_method}")

            wallet_methods = frozenset({'jazzcash', 'easypaisa'})
            if payment_method in wallet_methods:
                if not getattr(settings, 'WALLET_PAYMENT_SANDBOX', False):
                    return Response(
                        {"error": "Mobile wallet confirmation is unavailable (sandbox disabled)."},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE,
                    )
                otp_submitted = str(request.data.get('otp') or '').strip()
                expected_otp = str(getattr(settings, 'WALLET_SANDBOX_OTP', '4242'))
                if otp_submitted != expected_otp:
                    return Response(
                        {"error": f"Invalid OTP. In test mode enter the sandbox code ({expected_otp})."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                appointment.payment_status = 'pending'
                appointment.payment_id = transaction_id
                appointment.save()
                send_realtime_notification(
                    appointment.doctor.user.id,
                    {
                        "type": "payment_submitted",
                        "appointment_id": appointment.id,
                        "message": "Patient completed payment (wallet sandbox). Appointment is waiting for admin approval.",
                    },
                )

                return Response({
                    "message": "Sandbox wallet payment verified. Waiting for admin approval.",
                    "transaction_id": transaction_id,
                    "method": payment_method,
                }, status=status.HTTP_200_OK)

            # Retrieve the PaymentIntent from Stripe
            try:
                intent = stripe.PaymentIntent.retrieve(transaction_id)
                print(f"Intent retrieved: status={intent.status}, metadata={intent.metadata}")
            except stripe.error.InvalidRequestError as err:
                print(f"Stripe retrieval error for {transaction_id}: {str(err)}")
                return Response({"error": f"Payment intent not found: {str(err)}"}, status=status.HTTP_400_BAD_REQUEST)

            if not intent:
                return Response({"error": "Payment intent not found."}, status=status.HTTP_400_BAD_REQUEST)

            print(f"Intent status from Stripe: {intent.status}")
            
            # Accept both 'succeeded' and 'processing' statuses
            if intent.status not in ['succeeded', 'processing']:
                print(f"Payment not in acceptable status: status={intent.status}")
                return Response({
                    "error": f"Payment status is '{intent.status}'. Expected 'succeeded' or 'processing'.",
                    "payment_intent_status": intent.status
                }, status=status.HTTP_400_BAD_REQUEST)

            # Verify appointment metadata
            metadata = {}
            if intent and 'metadata' in intent:
                metadata = intent['metadata']
                if hasattr(metadata, 'to_dict'):
                    metadata = metadata.to_dict()

            intent_apt_id = ''
            if isinstance(metadata, dict):
                intent_apt_id = str(metadata.get('appointment_id', ''))
            elif metadata and 'appointment_id' in metadata:
                intent_apt_id = str(metadata['appointment_id'])

            print(f"Metadata check: intent_apt_id={intent_apt_id}, appointment.id={appointment.id}")
            
            if intent_apt_id != str(appointment.id):
                return Response({"error": f"Payment metadata mismatch: expected appointment {appointment.id}, got {intent_apt_id}."}, status=status.HTTP_400_BAD_REQUEST)

            # Keep payment pending until an admin approves/rejects it.
            appointment.payment_status = 'pending'
            appointment.payment_id = transaction_id
            appointment.save()
            print(f"Appointment updated: payment_status=pending, payment_id={transaction_id}")
            send_realtime_notification(
                appointment.doctor.user.id,
                {
                    "type": "payment_submitted",
                    "appointment_id": appointment.id,
                    "message": "Patient completed payment. Appointment is waiting for admin approval.",
                },
            )
            print(f"=== ConfirmPaymentView SUCCESS ===\n")

            return Response({
                "message": "Payment verified. Waiting for admin approval.",
                "transaction_id": transaction_id,
                "method": payment_method
            }, status=status.HTTP_200_OK)

        except Patient.DoesNotExist:
            print(f"Patient does not exist for user {request.user.id}")
            return Response({"error": "Patient profile not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            import traceback
            print(f"ConfirmPaymentView error: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            print(f"=== ConfirmPaymentView FAILED ===\n")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# 18.6 JazzCash — signed browser checkout link (HTTP POST page redirect)
class JazzCashCheckoutLinkView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        from django.core.signing import TimestampSigner
        from django.urls import reverse

        if request.user.user_type != 'patient':
            return Response(
                {"error": "Only patients can start JazzCash checkout."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            patient = Patient.objects.get(user=request.user)
        except Patient.DoesNotExist:
            return Response({"error": "Patient profile not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            appointment = Appointment.objects.get(id=pk, patient=patient)
        except Appointment.DoesNotExist:
            return Response({"error": "Appointment not found."}, status=status.HTTP_404_NOT_FOUND)

        if appointment.status == 'cancelled':
            return Response({"error": "Appointment is cancelled."}, status=status.HTTP_400_BAD_REQUEST)

        salt = getattr(settings, 'JAZZCASH_PAY_SIGNING_SALT', 'jazzcash-pay')
        signer = TimestampSigner(salt=salt)
        token = signer.sign(f"{pk}:{request.user.id}")
        rel = reverse('payments:jazzcash_start', kwargs={'token': token})
        checkout_url = request.build_absolute_uri(rel)

        return Response(
            {
                "checkout_url": checkout_url,
                "test_mode": getattr(settings, 'JAZZCASH_TEST_MODE', True),
                "instructions": "Open checkout_url in a browser, then click Pay Now to POST to JazzCash.",
            },
            status=status.HTTP_200_OK,
        )


# 19. CHAT API VIEW (FULLY UPGRADED FOR PERMANENT HISTORY)
class ChatAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser] 
    
    def get(self, request, pk):
        try:
            reference_apt = Appointment.objects.get(id=pk)
            
            messages = ChatMessage.objects.filter(
                appointment__doctor=reference_apt.doctor,
                appointment__patient=reference_apt.patient
            ).order_by('created_at')
            
            data = []
            for m in messages:
                msg_data = {
                    "sender_type": m.sender_type, 
                    "text": m.text, 
                    "time": m.time
                }
                if hasattr(m, 'attachment') and m.attachment:
                    msg_data["attachment"] = m.attachment.url
                data.append(msg_data)
                
            return Response(data, status=status.HTTP_200_OK)
            
        except Appointment.DoesNotExist:
            return Response({"error": "Appointment reference not found"}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request, pk):
        try:
            appointment = Appointment.objects.get(id=pk)
            
            chat_msg = ChatMessage(
                appointment=appointment,
                sender_type=request.user.user_type,
                text=request.data.get('text', ''),
                time=timezone.now().strftime("%I:%M %p")
            )
            
            attachment_file = request.FILES.get('attachment')
            if attachment_file:
                chat_msg.attachment = attachment_file
                
            chat_msg.save()
                
            return Response({"message": "Message sent"}, status=status.HTTP_201_CREATED)
        except Appointment.DoesNotExist:
            return Response({"error": "Appointment not found"}, status=status.HTTP_404_NOT_FOUND)


# 20. UPLOAD & GET PATIENT DOCUMENTS
class DocumentUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        if request.user.user_type != 'patient':
            return Response({"error": "Only patients can view documents."}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            patient = Patient.objects.get(user=request.user)
            documents = Document.objects.filter(patient=patient).order_by('-uploaded_at')
            serializer = DocumentSerializer(documents, many=True, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Patient.DoesNotExist:
            return Response({"error": "Patient profile not found."}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request):
        if request.user.user_type != 'patient':
            return Response({"error": "Only patients can upload documents."}, status=status.HTTP_403_FORBIDDEN)
        
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({"error": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            patient = Patient.objects.get(user=request.user)
            document = Document.objects.create(
                patient=patient,
                file=file_obj,
                filename=file_obj.name,
                file_size=file_obj.size
            )
            serializer = DocumentSerializer(document, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# 21. DELETE PATIENT DOCUMENT
class DocumentDeleteView(APIView):
    permission_classes = [IsAuthenticated]
    
    def delete(self, request, pk):
        try:
            patient = Patient.objects.get(user=request.user)
            document = Document.objects.get(id=pk, patient=patient)
            document.file.delete() 
            document.delete()      
            return Response({"message": "File deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
        except Document.DoesNotExist:
            return Response({"error": "Document not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



# 22. DOCTOR PAYOUT METHOD STATUS
class DoctorPayoutMethodView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.user_type != 'doctor':
            return Response({'error': 'Only doctors can access payout methods.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            doctor = Doctor.objects.get(user=request.user)
            method = DoctorPayoutMethod.objects.get(doctor=doctor)
            # Keep local flags in sync if account was completed in Stripe dashboard.
            # We only call Stripe when local state is still pending to avoid extra API calls.
            if method.stripe_account_id and (not method.charges_enabled or not method.details_submitted):
                try:
                    account = stripe.Account.retrieve(method.stripe_account_id)
                    method.charges_enabled = bool(account.charges_enabled)
                    method.details_submitted = bool(account.details_submitted)
                    method.save(update_fields=['charges_enabled', 'details_submitted'])
                except Exception:
                    # If Stripe sync fails, return stored state instead of breaking dashboard.
                    pass
            return Response({
                'stripe_account_id': method.stripe_account_id,
                'charges_enabled': method.charges_enabled,
                'details_submitted': method.details_submitted
            }, status=status.HTTP_200_OK)
        except DoctorPayoutMethod.DoesNotExist:
            return Response({'error': 'No payout method attached.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# 22a. GENERATE STRIPE CONNECT LINK
class GenerateStripeLinkView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.user_type != 'doctor':
            return Response({'error': 'Only doctors can use this.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            doctor = Doctor.objects.get(user=request.user)
            payout_method, created = DoctorPayoutMethod.objects.get_or_create(doctor=doctor)
            
            # 1. Create Express Account if not exists
            if not payout_method.stripe_account_id:
                account = stripe.Account.create(
                    type="express",
                    country="US",  # Adjust country as needed or make dynamic
                    email=request.user.email,
                    business_type="individual",
                    capabilities={
                        "card_payments": {"requested": True},
                        "transfers": {"requested": True},
                    },
                    business_profile={
                        "name": "MedTag",
                        "product_description": "Doctor consultation payments",
                        "support_email": "support@medtag.example",
                    },
                )
                payout_method.stripe_account_id = account.id
                payout_method.save()

            account = stripe.Account.retrieve(payout_method.stripe_account_id)

            # 2. If onboarding is already complete, open Express dashboard login
            if account.details_submitted and account.charges_enabled:
                login_link = stripe.Account.create_login_link(payout_method.stripe_account_id)
                return Response({"url": login_link.url}, status=status.HTTP_200_OK)

            # 3. Otherwise continue onboarding flow
            link = stripe.AccountLink.create(
                account=payout_method.stripe_account_id,
                refresh_url="http://localhost:3000/doctor-dashboard",
                return_url="http://localhost:3000/doctor-dashboard?stripe_callback=success",
                type="account_onboarding",
            )
            return Response({"url": link.url}, status=status.HTTP_200_OK)
        except stripe.error.InvalidRequestError as e:
            message = str(e)
            if "You can only create new accounts if you've signed up for Connect" in message:
                message = (
                    "Stripe Connect is not enabled for this Stripe account. "
                    "Please visit https://dashboard.stripe.com/connect and enable Connect, then retry."
                )
            return Response({"error": message}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

# 22b. VERIFY STRIPE ACCOUNT STATUS
class VerifyStripeAccountView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.user_type != 'doctor':
            return Response({'error': 'Access denied.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            doctor = Doctor.objects.get(user=request.user)
            payout_method = DoctorPayoutMethod.objects.get(doctor=doctor)
            
            if not payout_method.stripe_account_id:
                return Response({'error': 'No Stripe ID found.'}, status=status.HTTP_400_BAD_REQUEST)

            # Retrieve from Stripe
            account = stripe.Account.retrieve(payout_method.stripe_account_id)
            payout_method.charges_enabled = account.charges_enabled
            payout_method.details_submitted = account.details_submitted
            payout_method.save()

            return Response({
                'charges_enabled': payout_method.charges_enabled,
                'details_submitted': payout_method.details_submitted,
                'message': 'Account verified successfully.'
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request):
        if request.user.user_type != 'doctor':
            return Response({'error': 'Only doctors can delete payout methods.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            doctor = Doctor.objects.get(user=request.user)
            method = DoctorPayoutMethod.objects.get(doctor=doctor)
            method.delete()
            return Response({'message': 'Payout method deleted successfully.'}, status=status.HTTP_200_OK)
        except DoctorPayoutMethod.DoesNotExist:
            return Response({'error': 'No payout method found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# 23. DOCTOR EARNINGS ANALYTICS
class DoctorEarningsAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.user_type != 'doctor':
            return Response({'error': 'Only doctors can access earnings analytics.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            doctor = Doctor.objects.get(user=request.user)
            paid_appointments = Appointment.objects.filter(doctor=doctor, payment_status='paid')
            net_income = sum(float(apt.doctor.consultation_fee or 0) for apt in paid_appointments)
            
            withdrawal_requests = WithdrawalRequest.objects.filter(doctor=doctor).order_by('-requested_at')
            withdrawn_to_date = sum(float(w.amount) for w in withdrawal_requests if w.status == 'completed')
            pending_clearance = sum(float(w.amount) for w in withdrawal_requests if w.status == 'pending')
            
            available_for_withdrawal = max(0, net_income - (withdrawn_to_date + pending_clearance))
            
            history = [{'id': w.id, 'amount': float(w.amount), 'status': w.status, 'requested_at': w.requested_at.strftime('%Y-%m-%d %H:%M')} for w in withdrawal_requests]
            
            return Response({
                'net_income': round(net_income, 2),
                'withdrawn_to_date': round(withdrawn_to_date, 2),
                'pending_clearance': round(pending_clearance, 2),
                'available_for_withdrawal': round(available_for_withdrawal, 2),
                'withdrawal_history': history
            }, status=status.HTTP_200_OK)
        except Doctor.DoesNotExist:
            return Response({'error': 'Doctor profile not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# 24. DOCTOR WALLET - REQUEST WITHDRAWAL
class RequestWithdrawalView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.user_type != 'doctor':
            return Response({'error': 'Only doctors can request withdrawals.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            doctor = Doctor.objects.get(user=request.user)
            
            # 1. Validate Payout Method
            if not DoctorPayoutMethod.objects.filter(doctor=doctor).exists():
                return Response({'error': 'You must add a payout method first.'}, status=status.HTTP_400_BAD_REQUEST)
                
            amount = request.data.get('amount')
            if not amount:
                return Response({'error': 'Amount is required.'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                amount = float(amount)
            except (ValueError, TypeError):
                return Response({'error': 'Invalid amount.'}, status=status.HTTP_400_BAD_REQUEST)
            if amount <= 0:
                return Response({'error': 'Amount must be greater than zero.'}, status=status.HTTP_400_BAD_REQUEST)
                
            # 2. Validate Available Balance
            paid_appointments = Appointment.objects.filter(doctor=doctor, payment_status='paid')
            net_income = sum(float(apt.doctor.consultation_fee or 0) for apt in paid_appointments)
            existing = WithdrawalRequest.objects.filter(doctor=doctor, status__in=['pending', 'completed'])
            used_amount = sum(float(w.amount) for w in existing)
            available_for_withdrawal = max(0, net_income - used_amount)
            
            if amount > available_for_withdrawal:
                return Response({'error': f'Insufficient balance. Available: ${round(available_for_withdrawal, 2)}'}, status=status.HTTP_400_BAD_REQUEST)
                
            # 3. Create Request
            withdrawal = WithdrawalRequest.objects.create(doctor=doctor, amount=amount)
            return Response({'message': f'Withdrawal request of ${amount:.2f} submitted successfully!', 'withdrawal_id': withdrawal.id, 'status': withdrawal.status}, status=status.HTTP_201_CREATED)
        except Doctor.DoesNotExist:
            return Response({'error': 'Doctor profile not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdminOverviewView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        doctors = Doctor.objects.select_related('user').all()
        patients = Patient.objects.select_related('user').all()
        appointments = Appointment.objects.select_related('doctor__user', 'patient__user').order_by('-date_time')
        comments = ChatMessage.objects.select_related('appointment__doctor__user', 'appointment__patient__user').order_by('-created_at')

        doctors_payload = DoctorSerializer(doctors, many=True, context={'request': request}).data
        patients_payload = PatientSerializer(patients, many=True, context={'request': request}).data
        appointments_payload = AppointmentSerializer(appointments, many=True).data

        specialization_counter = {}
        for d in doctors:
            key = (d.specialization or 'General').strip()
            specialization_counter[key] = specialization_counter.get(key, 0) + 1
        doctors_by_specialization = [
            {"specialization": k, "count": v} for k, v in sorted(specialization_counter.items(), key=lambda x: x[0].lower())
        ]

        transactions = []
        paid_or_pending = appointments.filter(payment_status__in=['pending', 'paid', 'rejected'])
        for apt in paid_or_pending:
            transactions.append({
                "appointment_id": apt.id,
                "payment_id": apt.payment_id,
                "payment_status": apt.payment_status,
                "appointment_status": apt.status,
                "amount": float(apt.doctor.consultation_fee or 0),
                "date_time": apt.date_time,
                "patient_name": f"{apt.patient.user.first_name} {apt.patient.user.last_name}".strip(),
                "doctor_name": f"{apt.doctor.user.first_name} {apt.doctor.user.last_name}".strip(),
                "doctor_specialization": apt.doctor.specialization,
            })

        comments_payload = []
        for msg in comments:
            comments_payload.append({
                "id": msg.id,
                "appointment_id": msg.appointment_id,
                "sender_type": msg.sender_type,
                "text": msg.text,
                "time": msg.time,
                "created_at": msg.created_at,
                "attachment": msg.attachment.url if msg.attachment else None,
                "doctor_name": f"{msg.appointment.doctor.user.first_name} {msg.appointment.doctor.user.last_name}".strip(),
                "patient_name": f"{msg.appointment.patient.user.first_name} {msg.appointment.patient.user.last_name}".strip(),
            })

        return Response({
            "doctors_by_specialization": doctors_by_specialization,
            "doctors": doctors_payload,
            "patients": patients_payload,
            "appointments": appointments_payload,
            "pending_payment_approvals": [t for t in transactions if t["payment_status"] == "pending"],
            "transactions": transactions,
            "comments": comments_payload,
        }, status=status.HTTP_200_OK)


class AdminAppointmentManagementView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def put(self, request, pk):
        appointment = get_object_or_404(Appointment, pk=pk)
        data = request.data
        allowed_status = {'pending', 'confirmed', 'cancelled', 'completed'}
        allowed_payment = {'unpaid', 'pending', 'paid', 'rejected'}

        if 'date_time' in data:
            appointment.date_time = data.get('date_time')
        if 'status' in data:
            if data.get('status') not in allowed_status:
                return Response({"error": "Invalid appointment status."}, status=status.HTTP_400_BAD_REQUEST)
            appointment.status = data.get('status')
        if 'payment_status' in data:
            if data.get('payment_status') not in allowed_payment:
                return Response({"error": "Invalid payment status."}, status=status.HTTP_400_BAD_REQUEST)
            appointment.payment_status = data.get('payment_status')
        if 'clinical_notes' in data:
            appointment.clinical_notes = data.get('clinical_notes')
        if 'prescription' in data:
            appointment.prescription = data.get('prescription')

        appointment.save()
        return Response({"message": "Appointment updated by admin."}, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        appointment = get_object_or_404(Appointment, pk=pk)
        appointment.status = 'cancelled'
        appointment.save(update_fields=['status'])
        return Response({"message": "Appointment cancelled by admin."}, status=status.HTTP_200_OK)


class AdminPaymentDecisionView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, pk):
        appointment = get_object_or_404(Appointment, pk=pk)
        decision = request.data.get('decision')
        if decision not in ['approve', 'reject']:
            return Response({"error": "decision must be approve or reject."}, status=status.HTTP_400_BAD_REQUEST)

        if decision == 'approve':
            appointment.payment_status = 'paid'
            appointment.save(update_fields=['payment_status'])
            send_realtime_notification(
                appointment.patient.user.id,
                {
                    "type": "payment_decision",
                    "appointment_id": appointment.id,
                    "decision": "approved",
                    "message": "Your payment was approved by admin.",
                }
            )
            send_realtime_notification(
                appointment.doctor.user.id,
                {
                    "type": "payment_decision",
                    "appointment_id": appointment.id,
                    "decision": "approved",
                    "message": "A patient payment was approved by admin.",
                }
            )
            return Response({"message": "Payment approved by admin."}, status=status.HTTP_200_OK)

        appointment.payment_status = 'rejected'
        appointment.save(update_fields=['payment_status'])
        send_realtime_notification(
            appointment.patient.user.id,
            {
                "type": "payment_decision",
                "appointment_id": appointment.id,
                "decision": "rejected",
                "message": "Your payment was rejected by admin.",
            }
        )
        send_realtime_notification(
            appointment.doctor.user.id,
            {
                "type": "payment_decision",
                "appointment_id": appointment.id,
                "decision": "rejected",
                "message": "A patient payment was rejected by admin.",
            }
        )
        return Response({"message": "Payment rejected by admin."}, status=status.HTTP_200_OK)


class AdminChatMessageManagementView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def put(self, request, pk):
        message = get_object_or_404(ChatMessage, pk=pk)
        new_text = request.data.get('text', '')
        message.text = new_text
        message.save(update_fields=['text'])
        return Response({"message": "Comment updated by admin."}, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        message = get_object_or_404(ChatMessage, pk=pk)
        message.delete()
        return Response({"message": "Comment deleted by admin."}, status=status.HTTP_200_OK)


def _fan_out_reserve_notifications(result):
    if result.get("error"):
        return
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    doc_id = result["doctor_id"]

    def push(uid, payload):
        async_to_sync(channel_layer.group_send)(
            f"notifications_{uid}",
            {"type": "notification_message", "message": payload},
        )

    if result.get("doctor_event"):
        push(doc_id, result["doctor_event"])
    push(doc_id, result["doctor_queue_payload"])
    for uid in result["presence_targets"]:
        push(uid, result["presence_payload"])


def _fan_out_release_notifications(out):
    if out.get("error"):
        return
    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    def push(uid, payload):
        async_to_sync(channel_layer.group_send)(
            f"notifications_{uid}",
            {"type": "notification_message", "message": payload},
        )

    qr = out.get("queue_ready")
    if qr and qr.get("user_id"):
        push(qr["user_id"], qr["payload"])
    dq = out["doctor_queue_payload"]
    push(dq["doctor_id"], dq)
    for uid in out["presence_targets"]:
        push(uid, out["presence_payload"])


class ReserveCallSlotView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        doctor_id = request.data.get("doctor_id")
        appointment_id = request.data.get("appointment_id")
        actor_role = request.data.get("actor_role")
        patient_name = (request.data.get("patient_name") or "").strip() or "Patient"

        try:
            appointment_id = int(appointment_id)
            doctor_id = int(doctor_id)
        except (TypeError, ValueError):
            return Response(
                {"detail": "doctor_id and appointment_id are required integers."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        appointment = get_object_or_404(
            Appointment.objects.select_related("patient__user", "doctor__user"),
            pk=appointment_id,
        )

        if actor_role == "patient":
            if request.user.user_type != "patient":
                return Response(
                    {"detail": "Only patients may use actor_role patient."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if appointment.patient.user_id != request.user.id:
                return Response({"detail": "Not your appointment."}, status=status.HTTP_403_FORBIDDEN)
            if appointment.doctor.user_id != doctor_id:
                return Response(
                    {"detail": "Doctor does not match this appointment."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        elif actor_role == "doctor":
            if request.user.user_type != "doctor":
                return Response(
                    {"detail": "Only doctors may use actor_role doctor."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if appointment.doctor.user_id != request.user.id:
                return Response({"detail": "Not your appointment."}, status=status.HTTP_403_FORBIDDEN)
            doctor_id = request.user.id
            pn = f"{appointment.patient.user.first_name} {appointment.patient.user.last_name}".strip()
            if pn:
                patient_name = pn

        else:
            return Response(
                {"detail": 'actor_role must be "patient" or "doctor".'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = reserve_call_slot(
            doctor_id=doctor_id,
            appointment_id=appointment_id,
            patient_id=None,
            patient_name=patient_name,
            actor_role=actor_role,
            auth_user_id=request.user.id,
        )
        if result.get("error"):
            return Response(
                {"detail": result.get("detail", "Request denied.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        _fan_out_reserve_notifications(result)
        return Response(result["requester_payload"], status=status.HTTP_200_OK)


class ReleaseCallSlotView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        doctor_id = request.data.get("doctor_id")
        appointment_id = request.data.get("appointment_id")
        try:
            appointment_id = int(appointment_id)
            doctor_id = int(doctor_id)
        except (TypeError, ValueError):
            return Response(
                {"detail": "doctor_id and appointment_id are required integers."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        appointment = get_object_or_404(
            Appointment.objects.select_related("patient__user", "doctor__user"),
            pk=appointment_id,
        )

        if request.user.user_type == "patient":
            if appointment.patient.user_id != request.user.id:
                return Response({"detail": "Not your appointment."}, status=status.HTTP_403_FORBIDDEN)
            if appointment.doctor.user_id != doctor_id:
                return Response({"detail": "Doctor mismatch."}, status=status.HTTP_400_BAD_REQUEST)
        elif request.user.user_type == "doctor":
            if appointment.doctor.user_id != request.user.id:
                return Response({"detail": "Not your appointment."}, status=status.HTTP_403_FORBIDDEN)
            doctor_id = request.user.id
        else:
            return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)

        out = release_call_slot(doctor_id=doctor_id, appointment_id=appointment_id)
        if out.get("error"):
            return Response({"detail": "Invalid release."}, status=status.HTTP_400_BAD_REQUEST)

        _fan_out_release_notifications(out)
        return Response({"ok": True}, status=status.HTTP_200_OK)
