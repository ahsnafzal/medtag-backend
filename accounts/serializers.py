from rest_framework import serializers
from django.core.files.storage import default_storage
from .models import User, Patient, Doctor, Appointment
from django.contrib.auth import get_user_model
import re
from datetime import date

from .models import Document


User = get_user_model()

# UserSerializer
class UserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()

    def get_role(self, obj):
        if obj.is_superuser or obj.is_staff:
            return 'admin'
        return obj.user_type

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'mobile_number',
            'gender', 'user_type', 'profile_pic', 'is_staff', 'is_superuser',
            'is_active', 'role'
        ]

# PatientSerializer
class PatientSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    class Meta:
        model = Patient
        fields = ['user', 'blood_group', 'height', 'weight']
    
    def validate(self, data):
        if 'height' in data and data['height'] is not None:
            if data['height'] <= 0 or data['height'] > 300:
                raise serializers.ValidationError({"height": "Height must be valid"})
        if 'weight' in data and data['weight'] is not None:
            if data['weight'] <= 0 or data['weight'] > 300:
                raise serializers.ValidationError({"weight": "Weight must be valid"})
        return data

# DoctorSerializer
class DoctorSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    class Meta:
        model = Doctor
        fields = ['user', 'specialization', 'license_number', 'hospital', 'experience_years', 'consultation_fee', 'availability', 'license_front_image', 'license_back_image']

# ProfileUpdateSerializer
class ProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'email', 'profile_pic', 'first_name', 'last_name', 'avatar_url',
                  'mobile_number', 'user_type', 'gender', 'birthday')
        read_only_fields = ('email', 'is_superuser', 'is_staff')

    def update(self, instance, validated_data):
        validated_data.pop('is_superuser', None)
        profile_pic = validated_data.get('profile_pic')
        if profile_pic:
            if instance.profile_pic:
                default_storage.delete(instance.profile_pic.name)
            instance.profile_pic = profile_pic
        return super().update(instance, validated_data)

# ChangePasswordSerializer
class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)

# UserRegistrationSerializer - UPDATED
class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)
    phone = serializers.CharField(max_length=15, write_only=True)
    date_of_birth = serializers.DateField(write_only=True)
    
    # Patient fields
    blood_group = serializers.CharField(max_length=5, required=False, allow_blank=True)
    height = serializers.FloatField(required=False, allow_null=True)
    weight = serializers.FloatField(required=False, allow_null=True)
    
    # Doctor fields
    specialization = serializers.CharField(required=False, allow_blank=True)
    license_number = serializers.CharField(required=False, allow_blank=True)
    hospital = serializers.CharField(required=False, allow_blank=True)
    experience_years = serializers.FloatField(required=False, default=0.0)
    consultation_fee = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, default=0)
    

    # ✅ NEW: License Images

    # License Images

    license_front_image = serializers.ImageField(required=False, allow_null=True)
    license_back_image = serializers.ImageField(required=False, allow_null=True)
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'first_name', 'last_name',
            'password', 'confirm_password', 'user_type', 'gender',
            'phone', 'date_of_birth',
            'blood_group', 'height', 'weight',
            'specialization', 'license_number', 'hospital', 'experience_years', 'consultation_fee',
            'license_front_image', 'license_back_image' # Added images
        ]
        extra_kwargs = {'username': {'required': False}}

    # ✅ NEW: Explicitly handle the License Number format here so it matches the frontend
    def validate_license_number(self, value):
        user_type = self.initial_data.get('user_type')
        if user_type != 'doctor':
            return value

        if not value:
            raise serializers.ValidationError("PMDC License number is required for doctors.")

        # Clean the input (remove spaces, convert to uppercase)
        cleaned_value = str(value).strip().upper()

        # Regex: 1 to 10 digits, a hyphen, 1 to 5 letters (Matches exactly with frontend)
        pattern = r"^\d{1,10}-[A-Z]{1,5}$"
        
        if not re.match(pattern, cleaned_value):
            raise serializers.ValidationError(
                "License number format invalid or blacklisted. Use format like 12345-P or 1001-AJK."
            )

        return cleaned_value


    def validate(self, data):
        if data.get('password') != data.get('confirm_password'):
            raise serializers.ValidationError({"confirm_password": "Passwords do not match"})
        
        if User.objects.filter(email=data.get('email')).exists():
            raise serializers.ValidationError({"email": "Email already exists"})
        
        phone = data.get('phone', '')
        if phone and not re.match(r'^[\d\s\-\+\(\)]+$', phone):
            raise serializers.ValidationError({"phone": "Enter a valid phone number"})
        
        date_of_birth = data.get('date_of_birth')
        if date_of_birth and date_of_birth > date.today():
            raise serializers.ValidationError({"date_of_birth": "Date of birth cannot be in the future"})
        

        # Doctor Image Validation
        if data.get('user_type') == 'doctor':
             # Note: Images might be empty if user is testing without them, adjust if strictly required
             pass 

        return data
    
    def create(self, validated_data):
        phone = validated_data.pop('phone')
        date_of_birth = validated_data.pop('date_of_birth')
        validated_data.pop('confirm_password')
        
        # Extract patient fields
        blood_group = validated_data.pop('blood_group', '')
        height = validated_data.pop('height', None)
        weight = validated_data.pop('weight', None)
        
        # Extract doctor fields
        specialization = validated_data.pop('specialization', '')
        license_number = validated_data.pop('license_number', '')
        hospital = validated_data.pop('hospital', '')
        experience_years = validated_data.pop('experience_years', 0)
        consultation_fee = validated_data.pop('consultation_fee', 0)
        

        # ✅ Extract Images

        license_front = validated_data.pop('license_front_image', None)
        license_back = validated_data.pop('license_back_image', None)
        
        if 'username' not in validated_data:
            validated_data['username'] = validated_data['email']

        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            mobile_number=phone,
            birthday=date_of_birth,
            gender=validated_data.get('gender', ''),
            user_type=validated_data.get('user_type', 'patient')
        )
        
        if user.user_type == 'patient':
            Patient.objects.create(
                user=user,
                blood_group=blood_group,
                height=height,
                weight=weight
            )
        elif user.user_type == 'doctor':
            # ✅ Save images to Doctor model
            Doctor.objects.create(
                user=user,
                specialization=specialization,
                license_number=license_number,
                hospital=hospital,
                experience_years=experience_years,
                consultation_fee=consultation_fee,
                license_front_image=license_front, 
                license_back_image=license_back
            )
        

        return user

        return user
# Add this at the bottom of serializers.py
class AppointmentSerializer(serializers.ModelSerializer):
    patient_first_name = serializers.CharField(source='patient.user.first_name', read_only=True)
    patient_last_name = serializers.CharField(source='patient.user.last_name', read_only=True)
    patient_profile_pic = serializers.ImageField(source='patient.user.profile_pic', read_only=True)
    patient_id = serializers.IntegerField(source='patient.user.id', read_only=True)
    
    # Doctor information
    doctor_id = serializers.IntegerField(source='doctor.user.id', read_only=True)
    doctor_first_name = serializers.CharField(source='doctor.user.first_name', read_only=True)
    doctor_last_name = serializers.CharField(source='doctor.user.last_name', read_only=True)
    doctor_profile_pic = serializers.ImageField(source='doctor.user.profile_pic', read_only=True)
    doctor_specialization = serializers.CharField(source='doctor.specialization', read_only=True)
    doctor_hospital = serializers.CharField(source='doctor.hospital', read_only=True)
    doctor_consultation_fee = serializers.DecimalField(source='doctor.consultation_fee', max_digits=10, decimal_places=2, read_only=True)
    
    class Meta:
        model = Appointment
        fields = [
            'id', 
            'patient_first_name', 'patient_last_name', 'patient_profile_pic', 'patient_id',
            'doctor_id', 'doctor_first_name', 'doctor_last_name', 'doctor_profile_pic',
            'doctor_specialization', 'doctor_hospital', 'doctor_consultation_fee',
            'date_time', 'status', 'payment_status', 'symptoms', 'created_at', 'prescription'
        ]



class DocumentSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    
    class Meta:
        model = Document
        fields = ['id', 'filename', 'file_size', 'uploaded_at', 'url']
        
    def get_url(self, obj):
        request = self.context.get('request')
        if obj.file and hasattr(obj.file, 'url'):
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None


class AdminPatientProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = ['blood_group', 'height', 'weight']


class AdminDoctorProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Doctor
        fields = ['specialization', 'license_number', 'hospital', 'experience_years', 'consultation_fee', 'availability']


class AdminManagedUserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    patient_profile = serializers.SerializerMethodField()
    doctor_profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'mobile_number', 'gender', 'birthday',
            'user_type', 'role', 'is_active', 'is_staff', 'is_superuser', 'status',
            'created_at', 'patient_profile', 'doctor_profile'
        ]

    def get_role(self, obj):
        if obj.is_superuser or obj.is_staff:
            return 'admin'
        return obj.user_type

    def get_status(self, obj):
        return 'active' if obj.is_active else 'inactive'

    def get_patient_profile(self, obj):
        try:
            patient = Patient.objects.get(user=obj)
            return AdminPatientProfileSerializer(patient).data
        except Patient.DoesNotExist:
            return None

    def get_doctor_profile(self, obj):
        try:
            doctor = Doctor.objects.get(user=obj)
            return AdminDoctorProfileSerializer(doctor).data
        except Doctor.DoesNotExist:
            return None

