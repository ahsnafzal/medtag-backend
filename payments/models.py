from django.conf import settings
from django.db import models


class Payment(models.Model):
    """JazzCash (or future gateway) checkout attempt for an appointment.

    State machine (JazzCash hosted flow):
      initiated → user on JazzCash (card/CNIC/etc. entered there only, not in Django).
      succeeded → callback hash+code OK → appointment.payment_status paid, appointment confirmed.
      failed    → declined/error/cancel callback → appointment unchanged for retry.
    """

    GATEWAY_JAZZCASH = 'jazzcash'

    class Status(models.TextChoices):
        INITIATED = 'initiated', 'Initiated'
        SUCCEEDED = 'succeeded', 'Succeeded'
        FAILED = 'failed', 'Failed'

    gateway = models.CharField(max_length=32, default=GATEWAY_JAZZCASH, db_index=True)
    appointment = models.ForeignKey(
        'accounts.Appointment',
        on_delete=models.CASCADE,
        related_name='payments',
    )
    amount_major = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        help_text='Charge amount in PKR (major units) for bookkeeping.',
    )
    amount_minor = models.PositiveBigIntegerField(
        help_text='Amount sent to JazzCash (minor units, e.g. paisas).',
    )
    currency = models.CharField(max_length=3, default='PKR')
    merchant_txn_ref = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text='Merchant reference (pp_TxnRefNo).',
    )
    gateway_txn_id = models.CharField(
        max_length=128,
        blank=True,
        help_text='Gateway reference when available (e.g. Retrieval / auth code composite).',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.INITIATED,
        db_index=True,
    )

    jazzcash_response_code = models.CharField(max_length=16, blank=True)
    jazzcash_response_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.gateway} {self.merchant_txn_ref} ({self.status})'


class GatewayTransactionLog(models.Model):
    """Audit trail for gateway POST payloads (credentials redacted in code)."""

    class Direction(models.TextChoices):
        OUTBOUND = 'outbound', 'Outbound (to JazzCash)'
        INBOUND = 'inbound', 'Inbound (return URL POST)'

    payment = models.ForeignKey(
        Payment,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='gateway_logs',
    )
    appointment = models.ForeignKey(
        'accounts.Appointment',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='gateway_logs',
    )
    direction = models.CharField(max_length=16, choices=Direction.choices)
    gateway = models.CharField(max_length=32, default=Payment.GATEWAY_JAZZCASH)
    raw_payload = models.JSONField(default=dict)
    verified_hash = models.BooleanField(null=True, help_text='Null if hash not applicable.')

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)
