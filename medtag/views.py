from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from .models import UserDocument
from rest_framework.permissions import IsAuthenticated, AllowAny
import socket

from .serializer import UserDocumentSerializer, ReviewSerializer
from medtag.models import Review, Appointment, Doctor
import datetime # ✅ Added for date/time handling
from django.utils import timezone

class FileUploadAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, format=None):
        print("REQUEST DATA:", request.data)
        print("REQUEST FILES:", request.FILES)

        user = request.user
        file = request.FILES.get('file')

        if not file:
            return Response({"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)

        document = UserDocument.objects.create(user=user, filename=file.name, document=file)

        return Response({
            "message": "File uploaded successfully",
            "document_id": document.id
        }, status=status.HTTP_200_OK)

    def get(self, request):
        documents = UserDocument.objects.filter(user=request.user)
        serializer = UserDocumentSerializer(documents, many=True)
        return Response(serializer.data)

    def delete(self, request, pk, format=None):
        try:
            document = UserDocument.objects.get(id=pk, user=request.user)
            document.document.delete() # Deletes file from local storage
            document.delete()          # Deletes record from database
            return Response({"message": "File deleted successfully"}, status=status.HTTP_204_NO_CONTENT)
        except UserDocument.DoesNotExist:
            return Response({"error": "File not found"}, status=status.HTTP_404_NOT_FOUND)


class ReviewCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        appointment_id = request.data.get('appointment_id')
        rating = request.data.get('rating')
        comment = request.data.get('comment')

        try:
            appointment = Appointment.objects.get(id=appointment_id, patient__user=request.user)
            
            # ✅ UPDATE OR CREATE REVIEW
            # Is se purana review replace ho jayega aur naya add ho jayega
            review, created = Review.objects.update_or_create(
                doctor=appointment.doctor,
                patient=appointment.patient,
                defaults={
                    'appointment': appointment,
                    'rating': rating,
                    'comment': comment
                }
            )
            msg = "Review submitted successfully" if created else "Previous review updated successfully"
            return Response({"message": msg}, status=status.HTTP_201_CREATED)
            
        except Appointment.DoesNotExist:
            return Response({"error": "Invalid appointment"}, status=status.HTTP_404_NOT_FOUND)

class DoctorReviewListView(APIView):
    # This can be public or authenticated based on your preference
    def get(self, request):
        doctor_id = request.query_params.get('doctor_id')
        if not doctor_id:
            return Response({"error": "doctor_id is required"}, status=status.HTTP_400_BAD_REQUEST)
            
        reviews = Review.objects.filter(doctor__user__id=doctor_id).order_by('-created_at')
        serializer = ReviewSerializer(reviews, many=True)
        return Response(serializer.data)


# ==========================================
# ✅ PHASE 1: BULLETPROOF SLOT BLOCKING API
# ==========================================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_booked_slots(request):
    doctor_id = request.GET.get('doctor_id')
    date_str = request.GET.get('date') # Format: YYYY-MM-DD

    if not doctor_id or not date_str:
        return Response({"error": "doctor_id and date are required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # 1. Safely Find Doctor (Handles both User ID and Doctor ID)
        doctor = Doctor.objects.filter(id=doctor_id).first()
        if not doctor:
            doctor = Doctor.objects.filter(user__id=doctor_id).first()
            
        if not doctor:
            return Response({"booked_slots": []}, status=status.HTTP_200_OK)

        # 2. Get ALL active appointments for this doctor 
        # (Is se Timezone date shifting ka masla hamesha ke liye khatam ho jayega)
        appointments = Appointment.objects.filter(
            doctor=doctor
        ).exclude(status__in=['cancelled', 'rejected'])

        booked_times = []
        
        for apt in appointments:
            # A. Get Raw Database Time (UTC)
            raw_time = apt.date_time.strftime('%H:%M')
            raw_date = apt.date_time.strftime('%Y-%m-%d')
            
            # B. Get Local Time (PKT)
            try:
                local_dt = timezone.localtime(apt.date_time)
                local_time = local_dt.strftime('%H:%M')
                local_date = local_dt.strftime('%Y-%m-%d')
            except Exception:
                local_time = raw_time
                local_date = raw_date

            # C. Agar Date match karti hai (kisi bhi timezone mein), toh time block kar do!
            if date_str == raw_date or date_str == local_date:
                booked_times.append(raw_time)
                booked_times.append(local_time)

        # Remove duplicate times from the list
        booked_times = list(set(booked_times))
        
        # 👇 CHECK TERMINAL: Yeh aapke Django terminal mein print hoga!
        print(f"🚀 BULLETPROOF SLOTS BLOCKED for {date_str}: {booked_times}")

        return Response({"booked_slots": booked_times}, status=status.HTTP_200_OK)

    except Exception as e:
        print("ERROR IN GET_BOOKED_SLOTS:", str(e))
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==========================================
# ✅ LAN IP ENDPOINT (for QR Code generation)
# ==========================================
@api_view(['GET'])
@permission_classes([AllowAny])
def get_server_ip(request):
    """
    Returns the server's real LAN IP address so the React frontend
    can build scannable QR codes that work on mobile devices.
    Uses a UDP trick (no data sent) to determine the outbound IP.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))   # connects to Google DNS — no data is sent
        lan_ip = s.getsockname()[0]
        s.close()
    except Exception:
        lan_ip = "127.0.0.1"
    return Response({"ip": lan_ip, "port": 8000})