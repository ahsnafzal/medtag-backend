from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import UserDocument
from rest_framework.permissions import IsAuthenticated
from .serializer import UserDocumentSerializer

class FileUploadAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, format=None):
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
