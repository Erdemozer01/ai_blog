from django.contrib import admin
from django.utils.html import format_html
from .models import (GeneratedArticle, APIKey, Category, ContactMessage,
                     Profile, WorkExperience, Education, Skill)

@admin.register(GeneratedArticle)
class GeneratedArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'status', 'view_count', 'likes', 'dislikes', 'created_at')
    list_filter = ('status', 'owner', 'category')
    search_fields = ('title', 'user_request', 'full_content')

@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ('service_name', 'is_active', 'created_at')
    list_filter = ('is_active',)


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    # Listede görünecek alanlar
    list_display = ('subject', 'name', 'email', 'created_at', 'is_read')
    # Sağ tarafta filtreleme seçenekleri
    list_filter = ('is_read', 'created_at')
    # Arama çubuğunda hangi alanlarda arama yapılacağı
    search_fields = ('name', 'email', 'subject', 'message')
    # Tüm alanları sadece okunabilir yap, değiştirilmesini engelle
    readonly_fields = ('name', 'email', 'subject', 'message', 'created_at')

admin.site.register(Category)

# İlişkili modeller için inline admin sınıfları
class WorkExperienceInline(admin.StackedInline):
    model = WorkExperience
    extra = 1 # Varsayılan olarak 1 tane boş ekleme alanı gösterir

class EducationInline(admin.StackedInline):
    model = Education
    extra = 1

class SkillInline(admin.TabularInline): # TabularInline daha kompakt bir görünüm sunar
    model = Skill
    extra = 3

# Ana Profile admin sınıfı
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    inlines = [WorkExperienceInline, EducationInline, SkillInline]

    def image_preview(self, obj):
        if obj.profile_picture:
            return format_html('<img src="{}" width="50" height="50" style="object-fit: cover; border-radius: 50%;" />',
                               obj.profile_picture.url)
        return "Resim Yok"

    image_preview.short_description = 'Resim Önizleme'
    list_display = ('user', 'first_name', 'last_name', 'title', 'image_preview')

