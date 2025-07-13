from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html

from .models import (GeneratedArticle, APIKey, Category, ContactMessage,
                     Profile, WorkExperience, Education, Skill)


@admin.register(GeneratedArticle)
class GeneratedArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'category', 'status', 'view_count', 'likes', 'dislikes', 'created_at')
    list_filter = ('status', 'owner', 'category', 'created_at')
    search_fields = ('title', 'user_request', 'full_content')
    readonly_fields = ('view_count', 'likes', 'dislikes', 'created_at', 'slug')
    list_per_page = 25
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)

    fieldsets = (
        ('Temel Bilgiler', {
            'fields': ('title', 'category', 'owner', 'status', 'slug')
        }),
        ('İçerik', {
            'fields': ('user_request', 'keywords', 'english_abstract', 'turkish_abstract', 'full_content',
                       'bibliography'),
            'classes': ('collapse',)
        }),
        ('İstatistikler', {
            'fields': ('view_count', 'likes', 'dislikes', 'created_at'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('category', 'owner')

@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ('service_name', 'is_active', 'created_at', 'key_preview')
    list_filter = ('is_active', 'service_name')
    readonly_fields = ('created_at',)

    def key_preview(self, obj):
        if obj.key:
            return f"{obj.key[:8]}...{obj.key[-4:]}"
        return "Anahtar yok"

    key_preview.short_description = 'Anahtar Önizleme'


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'article_count', 'created_at')
    search_fields = ('name',)
    readonly_fields = ('created_at',)

    def article_count(self, obj):
        return obj.articles.count()

    article_count.short_description = 'Makale Sayısı'

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            article_count=Count('id')
        )

@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('subject', 'name', 'email', 'created_at', 'is_read', 'message_preview')
    list_filter = ('is_read', 'created_at')
    search_fields = ('name', 'email', 'subject', 'message')
    readonly_fields = ('name', 'email', 'subject', 'message', 'created_at')
    actions = ['mark_as_read', 'mark_as_unread']
    list_per_page = 20
    date_hierarchy = 'created_at'

    def message_preview(self, obj):
        return obj.message[:50] + "..." if len(obj.message) > 50 else obj.message

    message_preview.short_description = 'Mesaj Önizleme'

    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)

    mark_as_read.short_description = "Seçili mesajları okundu olarak işaretle"

    def mark_as_unread(self, request, queryset):
        queryset.update(is_read=False)

    mark_as_unread.short_description = "Seçili mesajları okunmadı olarak işaretle"

# İlişkili modeller için inline admin sınıfları
class WorkExperienceInline(admin.StackedInline):
    model = WorkExperience
    extra = 0  # Varsayılan boş alan sayısını azalt
    fields = ('job_title', 'company', 'start_date', 'end_date', 'description', 'order')

class EducationInline(admin.StackedInline):
    model = Education
    extra = 0
    fields = ('degree', 'institution', 'start_date', 'end_date', 'description', 'order')


class SkillInline(admin.TabularInline):
    model = Skill
    extra = 0
    fields = ('name', 'level', 'category', 'order')

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'first_name', 'last_name', 'title', 'image_preview')
    search_fields = ('user__username', 'first_name', 'last_name', 'title')
    readonly_fields = ('image_preview',)
    inlines = [WorkExperienceInline, EducationInline, SkillInline]

    fieldsets = (
        ('Kullanıcı Bilgileri', {
            'fields': ('user', 'first_name', 'last_name', 'title')
        }),
        ('Profil Resmi', {
            'fields': ('profile_picture', 'image_preview')
        }),
        ('İletişim', {
            'fields': ('email', 'linkedin_url', 'github_url')
        }),
        ('Hakkında', {
            'fields': ('summary',)
        }),
    )

    def image_preview(self, obj):
        if obj.profile_picture:
            return format_html(
                '<img src="{}" width="100" height="100" style="object-fit: cover; border-radius: 50%;" />',
                obj.profile_picture.url
            )
        return "Resim Yok"
    image_preview.short_description = 'Resim Önizleme'


# Admin site customization
admin.site.site_header = "AI Blog Yönetim Paneli"
admin.site.site_title = "AI Blog Yönetim Portalı"
admin.site.index_title = "Yönetim Paneline Hoş Geldiniz"
