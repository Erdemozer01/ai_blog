from django.contrib import admin

from .models import Provider, AIModel, APIKey


class APIKeyInline(admin.TabularInline):
    model = APIKey
    extra = 1
    fields = ('label', 'key', 'is_active', 'usage_count', 'last_used')
    readonly_fields = ('usage_count', 'last_used')
    verbose_name = "API Anahtarı"
    verbose_name_plural = "API Anahtarları (havuz)"


class AIModelInline(admin.TabularInline):
    model = AIModel
    extra = 1
    fields = ('model_name', 'label', 'is_active')
    verbose_name = "Model"
    verbose_name_plural = "Modeller"


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    list_display = ('service_name', 'is_active', 'active_model_count', 'active_key_count', 'created_at')
    list_filter = ('is_active',)
    list_editable = ('is_active',)
    readonly_fields = ('created_at',)
    inlines = [AIModelInline, APIKeyInline]


@admin.register(AIModel)
class AIModelAdmin(admin.ModelAdmin):
    list_display = ('provider', 'model_name', 'label', 'is_active', 'created_at')
    list_filter = ('is_active', 'provider')
    list_editable = ('is_active',)
    readonly_fields = ('created_at',)


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ('provider', 'label', 'is_active', 'usage_count', 'last_used', 'created_at')
    list_filter = ('is_active', 'provider')
    readonly_fields = ('created_at', 'usage_count', 'last_used')
    list_editable = ('is_active',)
    ordering = ('usage_count',)
