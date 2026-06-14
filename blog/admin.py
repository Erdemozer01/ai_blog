from django.contrib import admin
from django.utils.html import format_html
from django.contrib import messages

from .models import (GeneratedArticle, Category, ContactMessage,
                     Profile, WorkExperience, Education, Skill)


@admin.register(GeneratedArticle)
class GeneratedArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'category', 'status', 'view_count', 'cover_image_preview')
    list_filter = ('status', 'category', 'created_at')
    search_fields = ('title', 'user_request', 'full_content')
    readonly_fields = ('view_count', 'likes', 'dislikes', 'created_at', 'slug', 'cover_image_preview')
    list_per_page = 25
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)

    fieldsets = (
        ('Temel Bilgiler', {
            'fields': ('title', 'category', 'owner', 'status', 'slug', 'cover_image', 'cover_image_preview')
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

    def cover_image_preview(self, obj):
        if obj.cover_image:
            return format_html('<img src="{}" width="150" />', obj.cover_image.url)
        return "Fotoğraf Yok"

    cover_image_preview.short_description = 'Kapak Fotoğrafı Önizlemesi'

    def get_queryset(self, request):
        """Superuser tüm makaleleri görür; normal staff yalnızca kendi makalelerini."""
        qs = super().get_queryset(request).select_related('category', 'owner')
        if request.user.is_superuser:
            return qs
        return qs.filter(owner=request.user)

    def get_list_filter(self, request):
        """Superuser owner'a göre filtreleyebilir; normal kullanıcıya owner filtresi gösterme."""
        if request.user.is_superuser:
            return ('status', 'owner', 'category', 'created_at')
        return ('status', 'category', 'created_at')

    def get_readonly_fields(self, request, obj=None):
        """Normal kullanıcı 'owner' alanını değiştiremesin (otomatik kendisi)."""
        ro = list(self.readonly_fields)
        if not request.user.is_superuser:
            ro.append('owner')
        return ro

    def save_model(self, request, obj, form, change):
        """Yeni makale oluştururken sahibi otomatik olarak mevcut kullanıcı olsun."""
        if not change and not obj.owner_id:
            obj.owner = request.user
        # Normal kullanıcı başkasının makalesini kendi üstüne geçiremez
        if not request.user.is_superuser:
            obj.owner = request.user
        super().save_model(request, obj, form, change)

    def has_change_permission(self, request, obj=None):
        """Normal kullanıcı yalnızca kendi makalesini düzenleyebilir."""
        if obj is None or request.user.is_superuser:
            return super().has_change_permission(request, obj)
        return obj.owner_id == request.user.id

    def has_delete_permission(self, request, obj=None):
        """Normal kullanıcı yalnızca kendi makalesini silebilir."""
        if obj is None or request.user.is_superuser:
            return super().has_delete_permission(request, obj)
        return obj.owner_id == request.user.id




@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)
    readonly_fields = ('created_at',)


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('subject', 'name', 'email', 'created_at', 'is_read', 'message_preview')
    list_filter = ('is_read', 'created_at')
    search_fields = ('name', 'email', 'subject', 'message')
    readonly_fields = ('name', 'email', 'subject', 'message', 'created_at')
    actions = ['mark_as_read', 'mark_as_unread']
    list_per_page = 20
    date_hierarchy = 'created_at'

    # --- YENİ FONKSİYON EKLENDİ ---
    def change_view(self, request, object_id, form_url='', extra_context=None):
        """
        Admin düzenleme sayfası açıldığında bu fonksiyon çalışır.
        Eğer URL'de ?source=email varsa, mesajı okundu olarak işaretler.
        """
        # URL'yi kontrol et
        if request.GET.get('source') == 'email':
            try:
                # İlgili mesaj nesnesini al
                obj = self.get_object(request, object_id)
                if obj and not obj.is_read:
                    # Eğer okunmamışsa, okundu olarak işaretle ve kaydet
                    obj.is_read = True
                    obj.save(update_fields=['is_read'])
                    # Admin arayüzünde bir başarı mesajı göster
                    self.message_user(request, f"'{obj.subject}' başlıklı mesaj okundu olarak işaretlendi.",
                                      messages.SUCCESS)
            except Exception as e:
                self.message_user(request, f"Mesaj okundu olarak işaretlenirken bir hata oluştu: {e}", messages.ERROR)

        # Standart admin sayfasının yüklenmesine devam et
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    # --- YENİ FONKSİYON BİTTİ ---

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
    fields = ('degree', 'institution', 'graduation_year')


class SkillInline(admin.TabularInline):
    model = Skill
    extra = 0
    fields = ('name', 'level')


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