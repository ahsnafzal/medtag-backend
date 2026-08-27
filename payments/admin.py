
from django.contrib import admin

from .models import Payment, GatewayTransactionLog


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'gateway',
        'merchant_txn_ref',
        'status',
        'amount_major',
        'currency',
        'appointment',
        'created_at',
    )
    list_filter = ('gateway', 'status', 'currency')
    search_fields = ('merchant_txn_ref', 'gateway_txn_id', 'appointment__id')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(GatewayTransactionLog)
class GatewayTransactionLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'direction', 'gateway', 'payment', 'verified_hash', 'created_at')
    list_filter = ('direction', 'gateway')
    readonly_fields = ('created_at', 'raw_payload')
