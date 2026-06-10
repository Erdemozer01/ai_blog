from django.contrib import admin

from .models import Provider, APIKey


class APIKeyInline(admin.TabularInline):
    model = APIKey
    extra = 1
    fields = ('label', 'key', 'is_active', 'usage_count', 'last_used')
    readonly_fields = ('usage_count', 'last_used')


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    list_display = ('service_name', 'model_name', 'is_active', 'active_key_count', 'created_at')
    list_filter = ('is_active', 'service_name')
    list_editable = ('model_name', 'is_active')
    readonly_fields = ('created_at',)
    inlines = [APIKeyInline]


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ('provider', 'label', 'is_active', 'usage_count', 'last_used', 'created_at')
    list_filter = ('is_active', 'provider')
    readonly_fields = ('created_at', 'usage_count', 'last_used')
    list_editable = ('is_active',)
    ordering = ('usage_count',)