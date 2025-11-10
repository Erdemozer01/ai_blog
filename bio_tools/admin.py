from django.contrib import admin
from django.utils.html import format_html
from .models import AnalysisJob, FastqUpload


@admin.register(AnalysisJob)
class AnalysisJobAdmin(admin.ModelAdmin):
    list_display = ['job_id', 'file_name', 'colored_status',
                    'progress_bar', 'created_at', 'duration']
    list_filter = ['status', 'created_at']
    search_fields = ['job_id', 'file_name']
    readonly_fields = ['created_at', 'completed_at']

    def colored_status(self, obj):
        colors = {
            'PENDING': 'orange',
            'RUNNING': 'blue',
            'DONE': 'green',
            'ERROR': 'red',
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.status, 'black'),
            obj.get_status_display()
        )

    colored_status.short_description = 'Durum'

    def progress_bar(self, obj):
        return format_html(
            '<progress value="{}" max="100" style="width: 100px;"></progress> {}%',
            obj.progress, obj.progress
        )

    progress_bar.short_description = 'İlerleme'

    def duration(self, obj):
        if obj.total_duration:
            return f"{obj.total_duration:.2f}s"
        return "-"

    duration.short_description = 'Süre'


@admin.register(FastqUpload)
class FastqUploadAdmin(admin.ModelAdmin):
    list_display = ['id', 'file_short_name', 'colored_status',
                    'total_reads', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['id', 'file']
    readonly_fields = ['id', 'created_at', 'absolute_file_path']

    def file_short_name(self, obj):
        if obj.file:
            name = obj.file.name
            if len(name) > 50:
                return name[:47] + '...'
            return name
        return '-'

    file_short_name.short_description = 'Dosya'

    def colored_status(self, obj):
        colors = {
            'uploaded': 'blue',
            'counting': 'orange',
            'counted': 'green',
            'running': 'purple',
            'done': 'green',
            'count_error': 'red',
            'error': 'red',
        }
        return format_html(
            '<span style="color: {};">{}</span>',
            colors.get(obj.status, 'black'),
            obj.get_status_display()
        )

    colored_status.short_description = 'Durum'