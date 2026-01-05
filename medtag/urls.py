from django.urls import path
from.views import *

urlpatterns = [
        path('upload/', FileUploadAPIView.as_view(), name='file-upload'),
     ]