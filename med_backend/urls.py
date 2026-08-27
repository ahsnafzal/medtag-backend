from django.contrib import admin
from django.http import JsonResponse
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings
from ai.views import AISymptomMatchView, AIReportSummarizeView


def root(request):
    return JsonResponse({
        "service": "MedTag API",
        "admin": "/admin/",
        "api": "/api/",
        "pay": "/pay/",
    })


urlpatterns = [
    path('', root, name='root'),
    path('admin/', admin.site.urls),
    path('pay/', include('payments.urls')),
    path('api/ai/match-specialty/', AISymptomMatchView.as_view(), name='ai-symptom-match'),
    path('api/ai/summarize-report/', AIReportSummarizeView.as_view(), name='ai-summarize'),
    path('api/', include('medtag.urls')),
    path('api/', include('accounts.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)