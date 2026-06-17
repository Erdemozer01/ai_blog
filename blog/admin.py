from django.contrib import admin
from django.utils.html import format_html
from django.contrib import messages

from .models import (GeneratedArticle, Category, ContactMessage,
                     Profile, WorkExperience, Education, Skill)


class OnayBekleyenFilter(admin.SimpleListFilter):
    """Yayın onayı bekleyen makaleleri (talep var, henüz yayınlanmamış) filtreler."""
    title = 'Onay Durumu'
    parameter_name = 'onay_durumu'

    def lookups(self, request, model_admin):
        return (
            ('bekleyen', 'Onay bekleyen (talep var, yayında değil)'),
            ('yayinda', 'Yayında olanlar'),
            ('talepsiz', 'Talep göndermemiş olanlar'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'bekleyen':
            return queryset.filter(yayin_talebi=True, is_published=False)
        if self.value() == 'yayinda':
            return queryset.filter(is_published=True)
        if self.value() == 'talepsiz':
            return queryset.filter(yayin_talebi=False, is_published=False)
        return queryset


@admin.register(GeneratedArticle)
class GeneratedArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'category', 'status', 'yayin_talebi', 'is_published', 'ai_review_score', 'view_count', 'cover_image_preview')
    list_filter = ('status', 'category', 'created_at')
    search_fields = ('title', 'user_request', 'full_content')
    readonly_fields = ('view_count', 'likes', 'dislikes', 'created_at', 'slug', 'cover_image_preview',
                       'ai_review_score', 'ai_review_notes', 'ai_reviewed_at',
                       'reference_check_result', 'reference_checked_at')
    list_per_page = 25
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)

    fieldsets = (
        ('Temel Bilgiler', {
            'fields': ('title', 'category', 'owner', 'status', 'slug', 'cover_image', 'cover_image_preview')
        }),
        ('Yayın Durumu', {
            'fields': ('yayin_talebi', 'is_published'),
            'description': "Makalenizin anasayfada yayınlanması için 'Yayın için başvuruldu' kutusunu işaretleyin. "
                           "Yöneticiler başvurunuzu inceleyip onayladığında makaleniz anasayfada görünür."
        }),
        ('AI Yayınlanabilirlik İncelemesi', {
            'fields': ('ai_review_score', 'ai_review_notes', 'ai_reviewed_at'),
            'description': "Makaleyi AI ile incelemek için listede makaleyi seçip 'AI ile İncele' aksiyonunu çalıştırın. "
                           "Skor 0-100 arasıdır; öneriler kullanıcıya e-posta ile gönderilir."
        }),
        ('Kaynak Doğrulama (CrossRef)', {
            'fields': ('reference_check_result', 'reference_checked_at'),
            'description': "Kaynakların gerçekliğini CrossRef'te kontrol etmek için 'Kaynakları Doğrula' aksiyonunu çalıştırın. "
                           "Yalnızca kaynağın varlığını doğrular, atıf içeriğini değil.",
            'classes': ('collapse',)
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
        """Superuser owner ve yayın durumuna göre filtreleyebilir."""
        if request.user.is_superuser:
            return (OnayBekleyenFilter, 'yayin_talebi', 'is_published', 'status', 'owner', 'category', 'created_at')
        return ('status', 'category', 'created_at')

    def get_readonly_fields(self, request, obj=None):
        """Normal kullanıcı 'owner' ve 'is_published' alanlarını değiştiremesin.
        Kullanıcı yalnızca 'yayin_talebi' (başvuru) kutusunu işaretleyebilir;
        'is_published' (onay) yalnızca superuser tarafından değiştirilebilir."""
        ro = list(self.readonly_fields)
        if not request.user.is_superuser:
            ro.append('owner')
            ro.append('is_published')  # onayı sadece yönetici verir
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

    # --- Toplu onay aksiyonları (yalnızca superuser) ---
    actions = ['yayinla', 'yayindan_kaldir', 'ai_ile_incele', 'kaynaklari_dogrula', 'uydurma_kaynaklari_temizle']

    @admin.action(description="Seçili makaleleri YAYINLA (anasayfada göster)")
    def yayinla(self, request, queryset):
        if not request.user.is_superuser:
            self.message_user(request, "Bu işlem için yetkiniz yok.", level='error')
            return
        updated = queryset.update(is_published=True)
        self.message_user(request, f"{updated} makale yayınlandı (anasayfada görünür).")

    @admin.action(description="Seçili makaleleri YAYINDAN KALDIR")
    def yayindan_kaldir(self, request, queryset):
        if not request.user.is_superuser:
            self.message_user(request, "Bu işlem için yetkiniz yok.", level='error')
            return
        updated = queryset.update(is_published=False)
        self.message_user(request, f"{updated} makale yayından kaldırıldı.")

    @admin.action(description="🤖 AI ile İncele (skor + öneri + kullanıcıya e-posta)")
    def ai_ile_incele(self, request, queryset):
        if not request.user.is_superuser:
            self.message_user(request, "Bu işlem için yetkiniz yok.", level='error')
            return
        from .ai_review import review_article
        basarili, hatali = 0, 0
        for article in queryset:
            ok, msg = review_article(article)
            if ok:
                basarili += 1
                self.message_user(request, f"✓ '{article.title}': {msg}")
            else:
                hatali += 1
                self.message_user(request, f"✗ '{article.title}': {msg}", level='error')
        self.message_user(request, f"İnceleme bitti: {basarili} başarılı, {hatali} hatalı.")

    @admin.action(description="📚 Kaynakları Doğrula (CrossRef ile gerçeklik kontrolü)")
    def kaynaklari_dogrula(self, request, queryset):
        if not request.user.is_superuser:
            self.message_user(request, "Bu işlem için yetkiniz yok.", level='error')
            return
        from .reference_check import check_article_references
        basarili, hatali = 0, 0
        for article in queryset:
            ok, msg = check_article_references(article)
            if ok:
                basarili += 1
                self.message_user(request, f"✓ '{article.title}': {msg}")
            else:
                hatali += 1
                self.message_user(request, f"✗ '{article.title}': {msg}", level='warning')
        self.message_user(request, f"Doğrulama bitti: {basarili} başarılı, {hatali} atlandı.")

    @admin.action(description="🧹 Uydurma Kaynakları Temizle (yalnızca superuser makaleleri)")
    def uydurma_kaynaklari_temizle(self, request, queryset):
        if not request.user.is_superuser:
            self.message_user(request, "Bu işlem için yetkiniz yok.", level='error')
            return
        from .reference_check import clean_superuser_article_references
        temizlenen, atlanan = 0, 0
        for article in queryset:
            ok, msg = clean_superuser_article_references(article)
            if ok:
                temizlenen += 1
                self.message_user(request, f"✓ '{article.title}': {msg}")
            else:
                atlanan += 1
                self.message_user(request, f"✗ '{article.title}': {msg}", level='warning')
        self.message_user(request, f"Temizlik bitti: {temizlenen} işlendi, {atlanan} atlandı.")

    def get_actions(self, request):
        """Toplu yayın aksiyonlarını yalnızca superuser görsün."""
        actions = super().get_actions(request)
        if not request.user.is_superuser:
            actions.pop('yayinla', None)
            actions.pop('yayindan_kaldir', None)
            actions.pop('ai_ile_incele', None)
            actions.pop('kaynaklari_dogrula', None)
            actions.pop('uydurma_kaynaklari_temizle', None)
        return actions




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

    def get_queryset(self, request):
        """Superuser tüm profilleri görür; normal kullanıcı yalnızca kendi profilini."""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)

    def has_change_permission(self, request, obj=None):
        """Normal kullanıcı yalnızca kendi profilini düzenleyebilir."""
        if obj is None or request.user.is_superuser:
            return super().has_change_permission(request, obj)
        return obj.user_id == request.user.id

    def has_view_permission(self, request, obj=None):
        if obj is None or request.user.is_superuser:
            return super().has_view_permission(request, obj)
        return obj.user_id == request.user.id

    def get_readonly_fields(self, request, obj=None):
        """Normal kullanıcı 'user' alanını değiştiremesin."""
        ro = list(self.readonly_fields)
        if not request.user.is_superuser:
            ro.append('user')
        return ro