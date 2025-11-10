from rest_framework import serializers
from ..models import FastqUpload, AnalysisJob


class FastqUploadSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()
    file_size = serializers.SerializerMethodField()

    class Meta:
        model = FastqUpload
        fields = ['id', 'file', 'status', 'total_reads',
                  'created_at', 'download_url', 'file_size']
        read_only_fields = ['id', 'created_at']

    def get_download_url(self, obj):
        request = self.context.get('request')
        if obj.file:
            return request.build_absolute_uri(obj.file.url)
        return None

    def get_file_size(self, obj):
        if obj.file:
            size = obj.file.size
            # MB cinsinden
            return f"{size / (1024 * 1024):.2f} MB"
        return None


class AnalysisJobSerializer(serializers.ModelSerializer):
    progress_percentage = serializers.SerializerMethodField()
    duration_formatted = serializers.SerializerMethodField()

    class Meta:
        model = AnalysisJob
        fields = '__all__'
        read_only_fields = ['job_id', 'created_at', 'completed_at']

    def get_progress_percentage(self, obj):
        return f"{obj.progress}%"

    def get_duration_formatted(self, obj):
        if obj.total_duration:
            return f"{obj.total_duration:.2f}s"
        return None