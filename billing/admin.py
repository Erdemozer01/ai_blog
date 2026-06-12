from django.contrib import admin

from .models import UserCredit, CreditTransaction, ServicePrice


@admin.register(ServicePrice)
class ServicePriceAdmin(admin.ModelAdmin):
    list_display = ('label', 'service_key', 'cost', 'is_active')
    list_editable = ('cost', 'is_active')
    search_fields = ('label', 'service_key')


@admin.register(UserCredit)
class UserCreditAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance', 'updated_at')
    search_fields = ('user__username', 'user__email')
    list_editable = ('balance',)
    readonly_fields = ('updated_at',)


@admin.register(CreditTransaction)
class CreditTransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'transaction_type', 'description', 'created_at')
    list_filter = ('transaction_type', 'created_at')
    search_fields = ('user__username', 'description')
    readonly_fields = ('user', 'amount', 'transaction_type', 'description', 'created_at')
    date_hierarchy = 'created_at'
