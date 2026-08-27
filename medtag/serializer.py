from rest_framework import serializers
from .models import UserDocument

class UserDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserDocument
        fields = '__all__'
from medtag.models import Review
class UserDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserDocument
        fields = '__all__'



class ReviewSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.user.first_name', read_only=True)

    class Meta:
        model = Review
        fields = ['id', 'appointment', 'doctor', 'patient', 'patient_name', 'rating', 'comment', 'created_at']
        read_only_fields = ['patient', 'doctor']

