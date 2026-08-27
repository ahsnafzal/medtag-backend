from __future__ import annotations

import logging
import secrets
from datetime import timedelta
from urllib.parse import urlparse
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.db import transaction as db_transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from accounts.models import Appointment

from .models import GatewayTransactionLog, Payment
from .services.jazzcash import (
    build_secure_hash_hmac_hex,
    clean_mobile_digits,
    jazzcash_minor_amount,
    redact_sensitive_payload,
    verify_secure_hash_hmac,
)

logger = logging.getLogger(__name__)


def _unsign_pay_token(raw_token: str) -> tuple[int, int]:
    salt = getattr(settings, 'JAZZCASH_PAY_SIGNING_SALT', 'jazzcash-pay')
    signer = TimestampSigner(salt=salt)
    value = signer.unsign(raw_token, max_age=int(getattr(settings, 'JAZZCASH_PAY_LINK_MAX_AGE_SECONDS', 3600)))
    apt_id_str, uid_str = value.split(':', 1)
    return int(apt_id_str), int(uid_str)


def _absolute_return_url(request) -> str:
    base = (getattr(settings, 'PUBLIC_BASE_URL', '') or '').rstrip('/')
    path = reverse('payments:jazzcash_return')
    if base:
        return f'{base}{path}'
    return request.build_absolute_uri(path)


def _checkout_post_url() -> str:
    if getattr(settings, 'JAZZCASH_TEST_MODE', True):
        return getattr(
            settings,
            'JAZZCASH_SANDBOX_PAYMENT_POST_URL',
            'https://sandbox.jazzcash.com.pk/CustomerPortal/transactionmanagement/merchantform/',
        )
    return getattr(
        settings,
        'JAZZCASH_PRODUCTION_PAYMENT_POST_URL',
        'https://payments.jazzcash.com.pk/CustomerPortal/transactionmanagement/merchantform/',
    )


def _consultation_fee_pkr_minor(appointment: Appointment) -> tuple[Decimal, int]:
    fee_usd = appointment.doctor.consultation_fee
    if fee_usd is None:
        raise ValidationError('Consultation fee missing.')
    if Decimal(str(fee_usd)) <= 0:
        raise ValidationError('Consultation fee must be positive.')

    rate = Decimal(str(settings.JAZZCASH_USD_TO_PKR_RATE))
    amount_pkr = (Decimal(str(fee_usd)) * rate).quantize(Decimal('0.01'))
    minor = jazzcash_minor_amount(amount_pkr)
    return amount_pkr, minor


def _merchant_fields_for_checkout(
    *, appointment: Appointment, txn_ref: str, return_url: str, mobile: str
) -> tuple[dict[str, str], Decimal, int]:
    now = timezone.localtime(timezone.now())
    expiry = now + timedelta(days=3)

    amount_pkr, amount_minor = _consultation_fee_pkr_minor(appointment)

    merchant_id = (getattr(settings, 'JAZZCASH_MERCHANT_ID', '') or '').strip()
    password = getattr(settings, 'JAZZCASH_MERCHANT_PASSWORD', '') or ''

    salt = (getattr(settings, 'JAZZCASH_INTEGRITY_SALT', '') or '').strip()
    if not merchant_id or not password or not salt:
        raise ValidationError('JazzCash merchant credentials missing (set env / settings).')

    fields: dict[str, str] = {
        'pp_Language': 'EN',
        'pp_MerchantID': merchant_id,
        'pp_SubMerchantID': '',
        'pp_Password': password,
        'pp_BankID': '',
        'pp_ProductID': '',
        'pp_TxnRefNo': txn_ref,
        'pp_Amount': str(amount_minor),
        'pp_TxnCurrency': 'PKR',
        'pp_TxnDateTime': now.strftime('%Y%m%d%H%M%S'),
        'pp_TxnExpiryDateTime': expiry.strftime('%Y%m%d%H%M%S'),
        'pp_BillReference': str(appointment.id),
        'pp_Description': f'MedTag appointment {appointment.id}',
        'pp_TxnType': 'MWALLET',
        'pp_Version': '1.1',
        'pp_ReturnURL': return_url,
        'ppmpf_1': '',
        'ppmpf_2': '',
        'ppmpf_3': '',
        'ppmpf_4': '',
        'ppmpf_5': '',
    }
    if mobile:
        fields['pp_MobileNumber'] = mobile

    hash_source = {k: v for k, v in fields.items() if str(v).strip() != ''}
    fields['pp_SecureHash'] = build_secure_hash_hmac_hex(hash_source, salt)
    return fields, amount_pkr, amount_minor


@require_GET
def jazzcash_pay_start(request, token: str):
    """
    Build hosted-checkout fields and render "Pay Now" which POSTs the browser to JazzCash.

    Django does not collect or validate card numbers, CVV, wallet MPIN/CNIC, or OTP —
    JazzCash's hosted page handles all payer authentication. This view only prepares
    the signed initiation payload (incl. pp_SecureHash) and persists Payment=initiated.
    """
    try:
        appointment_id, user_id = _unsign_pay_token(token)
    except SignatureExpired:
        return render(
            request,
            'payments/jazzcash_error.html',
            {'message': 'This payment link has expired. Request a new link from the app.'},
            status=403,
        )
    except (BadSignature, ValueError):
        return render(request, 'payments/jazzcash_error.html', {'message': 'Invalid payment link.'}, status=403)

    appointment = get_object_or_404(Appointment, pk=appointment_id)
    if appointment.patient_id != user_id:
        return HttpResponseForbidden('Not allowed for this appointment.')

    if appointment.status == 'cancelled':
        return render(request, 'payments/jazzcash_error.html', {'message': 'This appointment is cancelled.'}, status=400)

    # Optional prefill from query string
    mobile = clean_mobile_digits(request.GET.get('mobile') or '')

    prefix = f'T{timezone.localtime(timezone.now()).strftime("%y%m%d%H%M%S")}'
    suffix = secrets.token_hex(3).upper()
    txn_ref = (prefix + suffix)[:24]

    return_url = _absolute_return_url(request)
    gateway_url = _checkout_post_url()

    try:
        fields, amount_pkr, amount_minor = _merchant_fields_for_checkout(
            appointment=appointment,
            txn_ref=txn_ref,
            return_url=return_url,
            mobile=mobile,
        )
    except ValidationError as exc:
        return render(request, 'payments/jazzcash_error.html', {'message': str(exc)}, status=400)

    with db_transaction.atomic():
        payment = Payment.objects.create(
            gateway=Payment.GATEWAY_JAZZCASH,
            appointment=appointment,
            amount_major=amount_pkr,
            amount_minor=amount_minor,
            currency='PKR',
            merchant_txn_ref=txn_ref,
            status=Payment.Status.INITIATED,
        )

        GatewayTransactionLog.objects.create(
            payment=payment,
            appointment=appointment,
            direction=GatewayTransactionLog.Direction.OUTBOUND,
            gateway=Payment.GATEWAY_JAZZCASH,
            raw_payload=redact_sensitive_payload(fields),
            verified_hash=None,
            notes=(
                'Hosted checkout POST payload. Sandbox “Getting Started → API Call Log” often logs '
                'only in-portal API simulator requests; hosted POSTs appear under Transaction Reports / '
                'Transaction Management.'
            ),
        )

    ru = urlparse(return_url)
    logger.info(
        'JazzCash outbound checkout prepared payment_id=%s txn_ref=%s post_to_host=%s return_host=%s',
        payment.id,
        txn_ref,
        urlparse(gateway_url).netloc,
        ru.netloc or '(relative)',
    )

    context = {
        'gateway_url': gateway_url,
        'fields': fields,
        'appointment': appointment,
        'payment': payment,
        'test_mode': bool(getattr(settings, 'JAZZCASH_TEST_MODE', True)),
        'pp_return_url': return_url,
        'localhost_return_warning': any(
            h in return_url.lower()
            for h in ('127.0.0.1', 'localhost', '0.0.0.0')
        ),
    }
    return render(request, 'payments/jazzcash_pay.html', context)


def _incoming_hash(data: dict[str, str]) -> str | None:
    return (
        data.get('pp_SecureHash')
        or data.get('pp_secureHash')
        or data.get('secureHash')
        or ''
    )


@csrf_exempt
@require_POST
def jazzcash_pay_return(request):
    """
    JazzCash POSTs the payment result to pp_ReturnURL (CSRF exempt: external gateway).

    Success path requires BOTH:
      - Integrity: HMAC/hash on returned fields matches (integrity salt).
      - Business: pp_ResponseCode == '000'.

    Only then: Payment=succeeded, Appointment.status=confirmed, appointment.payment_status=paid.
    Any other case: Payment=failed; appointment booking fields are left unchanged so the patient
    can retry. API/portal logs reflect activity after JazzCash completes the session and POSTs here.
    """
    payload = dict(request.POST.items())
    stripped = {k: (v.strip() if isinstance(v, str) else v) for k, v in payload.items()}

    txn_ref = stripped.get('pp_TxnRefNo') or ''

    incoming_secure = _incoming_hash(stripped)
    verify_bucket = dict(stripped)
    for hk in ('pp_SecureHash', 'pp_secureHash', 'secureHash'):
        verify_bucket.pop(hk, None)

    salt = (getattr(settings, 'JAZZCASH_INTEGRITY_SALT', '') or '').strip()
    verified = verify_secure_hash_hmac(verify_bucket, salt, incoming_secure) if salt else False

    response_code = (stripped.get('pp_ResponseCode') or stripped.get('responseCode') or '').strip()
    response_message = (
        stripped.get('pp_ResponseMessage')
        or stripped.get('responseMessage')
        or ''
    )

    success = bool(verified and response_code == '000')
    redirect_base = (getattr(settings, 'JAZZCASH_RESULT_FRONTEND_URL', '') or '').strip()

    logger.info(
        'JazzCash inbound return txn_ref=%s hash_ok=%s response_code=%s',
        txn_ref,
        verified,
        response_code,
    )

    payment = Payment.objects.filter(merchant_txn_ref=txn_ref).first()

    if not payment:
        GatewayTransactionLog.objects.create(
            payment=None,
            appointment=None,
            direction=GatewayTransactionLog.Direction.INBOUND,
            gateway=Payment.GATEWAY_JAZZCASH,
            raw_payload=redact_sensitive_payload(stripped),
            verified_hash=verified,
            notes='Return POST without matching Payment row.',
        )
        if redirect_base:
            return redirect(f'{redirect_base.rstrip("/")}?status=error&reason=unknown_txn')
        return render(
            request,
            'payments/jazzcash_result.html',
            {'success': False, 'message': 'Unknown transaction reference.', 'payload': stripped, 'hash_ok': verified},
            status=400,
        )

    gateway_id = (
        stripped.get('pp_RetrievalReferenceNo')
        or stripped.get('pp_AuthCode')
        or stripped.get('pp_TxnRefNo')
        or ''
    )

    with db_transaction.atomic():
        payment = Payment.objects.select_for_update().get(pk=payment.pk)

        if payment.status == Payment.Status.SUCCEEDED:
            GatewayTransactionLog.objects.create(
                payment=payment,
                appointment=payment.appointment,
                direction=GatewayTransactionLog.Direction.INBOUND,
                gateway=Payment.GATEWAY_JAZZCASH,
                raw_payload=redact_sensitive_payload(stripped),
                verified_hash=verified,
                notes='Duplicate return POST (payment already succeeded).',
            )
        else:

            GatewayTransactionLog.objects.create(
                payment=payment,
                appointment=payment.appointment,
                direction=GatewayTransactionLog.Direction.INBOUND,
                gateway=Payment.GATEWAY_JAZZCASH,
                raw_payload=redact_sensitive_payload(stripped),
                verified_hash=verified,
                notes=f'ResponseCode={response_code}; hash_ok={verified}',
            )

            payment.jazzcash_response_code = response_code[:16]
            payment.jazzcash_response_message = (response_message or '')[:2000]
            payment.gateway_txn_id = (gateway_id or '')[:128]

            apt = payment.appointment

            if success:
                payment.status = Payment.Status.SUCCEEDED
                payment.save(
                    update_fields=[
                        'status',
                        'jazzcash_response_code',
                        'jazzcash_response_message',
                        'gateway_txn_id',
                        'updated_at',
                    ]
                )
                apt.status = 'confirmed'
                apt.payment_status = 'paid'
                apt.payment_id = txn_ref or payment.merchant_txn_ref
                apt.save(update_fields=['status', 'payment_status', 'payment_id'])
            else:
                payment.status = Payment.Status.FAILED
                payment.save(
                    update_fields=[
                        'status',
                        'jazzcash_response_code',
                        'jazzcash_response_message',
                        'gateway_txn_id',
                        'updated_at',
                    ]
                )

    payment.refresh_from_db()

    if redirect_base:
        outcome_ok = payment.status == Payment.Status.SUCCEEDED
        q = f'status={"ok" if outcome_ok else "fail"}&appointment={payment.appointment_id}&txn={txn_ref}'
        if not verified:
            q += '&hash=invalid'
        return redirect(f'{redirect_base.rstrip("/")}?{q}')

    return render(
        request,
        'payments/jazzcash_result.html',
        {
            'success': payment.status == Payment.Status.SUCCEEDED,
            'hash_ok': verified,
            'response_code': response_code,
            'response_message': response_message,
            'appointment': payment.appointment,
            'payment': payment,
        },
    )
