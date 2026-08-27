from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html # ✅ Import for creating links
from .models import User, OTPCode, Doctor, Patient, Appointment, DoctorPayoutMethod

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    model = User
    list_display = ['email', 'username', 'first_name', 'last_name', 'user_type', 'mobile_number', 'gender', 'is_staff', 'is_active']
    list_filter = ['user_type', 'is_staff', 'is_active', 'created_at', 'gender']
    search_fields = ['email', 'username', 'first_name', 'last_name', 'mobile_number']
    ordering = ['email']
    
    fieldsets = UserAdmin.fieldsets + (
        ('Additional Info', {
            'fields': ('profile_pic', 'avatar_url', 'subscription_status', 'mobile_number', 'user_type', 'gender', 'birthday')
        }),
    )

@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    # ✅ Added 'verify_pmdc_link' to list_display
    list_display = ['get_full_name', 'license_number', 'verify_pmdc_link', 'specialization', 'hospital', 'experience_years']
    list_filter = ['specialization', 'hospital']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'specialization', 'license_number']
    
    readonly_fields = ['license_front_preview', 'license_back_preview', 'verify_pmdc_link_large']

    def get_email(self, obj):
        return obj.user.email
    get_email.short_description = 'Email'
    
    def get_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"
    get_full_name.short_description = 'Name'

    # ✅ NEW: Button to open PMDC Website for verification
    def verify_pmdc_link(self, obj):
        if obj.license_number:
            # Opens PMDC Search page in new tab
            return format_html(
                '<a class="button" href="https://pmdc.pk/Doctors/Search" target="_blank" '
                'style="background-color: #1D7D4B; color: white; padding: 5px 10px; border-radius: 5px; text-decoration: none; font-weight: bold;">'
                '🔍 Verify {license}</a>',
                license=obj.license_number
            )
        return "No License"
    
    verify_pmdc_link.short_description = "PMDC Verification"

    # Larger link for the details page
    def verify_pmdc_link_large(self, obj):
        if obj.license_number:
            return format_html(
                '<a href="https://pmdc.pk/Doctors/Search" target="_blank" '
                'style="font-size: 16px; color: #1D7D4B; font-weight: bold;">'
                '👉 Click here to verify License #{license} on Official PMDC Website</a>',
                license=obj.license_number
            )
        return "-"
    verify_pmdc_link_large.short_description = "Manual Verification"

    # Helper to show image preview in admin panel
    def license_front_preview(self, obj):
        if obj.license_front_image:
            return f'<img src="{obj.license_front_image.url}" width="300" style="border-radius: 10px; border: 2px solid #ddd;" />'
        return "No Image"
    
    def license_back_preview(self, obj):
        if obj.license_back_image:
            return f'<img src="{obj.license_back_image.url}" width="300" style="border-radius: 10px; border: 2px solid #ddd;" />'
        return "No Image"

@admin.register(OTPCode)
class OTPCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'user', 'expiration_time', 'otp_status', 'is_expired_display']
    list_filter = ['otp_status', 'expiration_time']
    search_fields = ['user__email', 'code']
    
    def is_expired_display(self, obj):
        return obj.is_expired()
    is_expired_display.boolean = True
    is_expired_display.short_description = 'Expired?'

@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ['get_full_name', 'get_email', 'blood_group', 'height', 'weight', 'get_gender', 'get_mobile_number']
    list_filter = ['blood_group']
    search_fields = ['user__email', 'user__first_name', 'user__last_name']
    
    def get_email(self, obj):
        return obj.user.email
    get_email.short_description = 'Email'
    get_email.admin_order_field = 'user__email'
    
    def get_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"
    get_full_name.short_description = 'Full Name'
    get_full_name.admin_order_field = 'user__first_name'
    
    def get_gender(self, obj):
        return obj.user.gender
    get_gender.short_description = 'Gender'
    get_gender.admin_order_field = 'user__gender'
    
    def get_mobile_number(self, obj):
        return obj.user.mobile_number
    get_mobile_number.short_description = 'Mobile Number'
    get_mobile_number.admin_order_field = 'user__mobile_number'

# Optional: If you added Appointment model back
@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):

    list_display = ['patient', 'doctor', 'date_time', 'status']
    list_filter = ['status', 'date_time']
    search_fields = ['patient__user__first_name', 'doctor__user__first_name']
    list_display = ('id', 'patient', 'doctor', 'date_time', 'status', 'payment_status')
    list_filter = ('status', 'payment_status')
    search_fields = ('patient__user__first_name', 'doctor__user__first_name')


# ✅ DOCTOR PAYOUT METHOD ADMIN
@admin.register(DoctorPayoutMethod)
class DoctorPayoutMethodAdmin(admin.ModelAdmin):
    list_display = ('doctor', 'stripe_account_id', 'charges_enabled', 'details_submitted', 'created_at')
    list_filter = ('charges_enabled', 'details_submitted', 'created_at')
    search_fields = ('doctor__user__email', 'doctor__user__first_name', 'doctor__user__last_name', 'stripe_account_id')
    readonly_fields = ('created_at',)
    
    def doctor(self, obj):
        return f"Dr. {obj.doctor.user.first_name} {obj.doctor.user.last_name}"
    doctor.short_description = 'Doctor Name'


