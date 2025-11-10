from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FastqUploadViewSet, AnalysisJobViewSet

router = DefaultRouter()
router.register(r'uploads', FastqUploadViewSet, basename='fastq-upload')
router.register(r'jobs', AnalysisJobViewSet, basename='analysis-job')

urlpatterns = [
    path('', include(router.urls)),
]