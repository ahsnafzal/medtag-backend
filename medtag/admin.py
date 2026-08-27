
from django.contrib import admin

from .models import UserDocument

from .models import UserDocument, Review


@admin.register(UserDocument)
class UserDocumentAdmin(admin.ModelAdmin):
    list_display = ['user', 'filename', 'uploaded_at']
    list_filter = ['uploaded_at']
    search_fields = ['user__email', 'filename']
# Register your models here.


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['appointment','doctor','patient','rating','comment']
    search_fields = ['patient']

