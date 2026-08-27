# MedTag Backend

MedTag Backend is a Django 4.2 API for a medical appointment platform. It supports patient and doctor accounts, appointment scheduling, medical documents, reviews, chat and live call sessions, doctor payouts, Stripe workflows, JazzCash hosted checkout, and authenticated AI-assisted medical routing and report summaries.

## Features

- JWT-authenticated REST API
- Patient and doctor profiles and dashboards
- Doctor discovery and appointment booking, cancellation, rescheduling, and status updates
- Medical document upload and deletion
- Appointment chat and live call/notification WebSockets
- Stripe payment and doctor payout workflows
- Hosted JazzCash checkout with signed requests and verified callbacks
- AI symptom-to-specialty matching
- AI summaries for image and PDF medical reports
- Django admin for operational management
- PostgreSQL database with local media storage

## Stack

- Python 3.10+
- Django 4.2
- Django REST Framework
- Simple JWT
- Django Channels, Daphne, and Redis
- PostgreSQL via `psycopg`
- Stripe and JazzCash integrations
- Google Generative AI
- Pillow and PyPDF2

## Project Layout

```text
med_backend/     Django settings, URL configuration, WSGI and ASGI entrypoints
accounts/        Users, profiles, appointments, chat, calls, payouts, and admin APIs
medtag/          Documents, reviews, file upload, and utility APIs
payments/        Payment models and JazzCash hosted checkout callbacks
ai/              Authenticated AI symptom and report endpoints
templates/       Django checkout, contact, and password-reset templates
media/           Runtime uploads; ignored by Git
manage.py        Django management entrypoint
requirements.txt Python dependencies
```

## Requirements

Install:

- Python 3.10 or newer
- PostgreSQL 13 or newer
- Redis 5 or newer for production WebSocket channel layers
- A Google Generative AI API key for AI endpoints
- Stripe credentials if Stripe features are used
- JazzCash merchant credentials if JazzCash is enabled

The development channel layer uses in-memory storage when `DEBUG=True`. Production should use Redis.

## Local Setup

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Create a `.env` file in the project root. Never commit it:

```dotenv
DB_NAME=medtag
DB_USER=postgres
DB_PASSWORD=change-me
DB_HOST=127.0.0.1
DB_PORT=5432

REACTAPP_RESET_URL=http://localhost:3000/reset-password
LOGIN_URI=http://localhost:3000/login
PUBLIC_BASE_URL=http://127.0.0.1:8000

STRIPE_SECRET_KEY=
STRIPE_PUBLISHABLE_KEY=
STRIPE_WEBHOOK_SECRET=

WALLET_PAYMENT_SANDBOX=True
WALLET_SANDBOX_OTP=4242

JAZZCASH_TEST_MODE=True
JAZZCASH_MERCHANT_ID=
JAZZCASH_MERCHANT_PASSWORD=
JAZZCASH_INTEGRITY_SALT=
JAZZCASH_USD_TO_PKR_RATE=278.00
JAZZCASH_PAY_SIGNING_SALT=replace-this
JAZZCASH_PAY_LINK_MAX_AGE_SECONDS=3600
JAZZCASH_RESULT_FRONTEND_URL=http://localhost:3000/payment/result
JAZZCASH_SANDBOX_PAYMENT_POST_URL=
JAZZCASH_PRODUCTION_PAYMENT_POST_URL=

GEMINI_API_KEY=
```

Create the PostgreSQL database named in `DB_NAME`, then run:

```powershell
python manage.py migrate
python manage.py createsuperuser
python manage.py check
python manage.py runserver
```

The API is available at `http://127.0.0.1:8000/`. The root endpoint returns links to the admin, API, and payment areas. Django serves uploaded media locally only when `DEBUG=True`.

## Authentication

The API uses JWT authentication. Send the access token on protected requests:

```http
Authorization: Bearer <access-token>
```

Start with:

```http
POST /api/register/
POST /api/verify-email/
POST /api/login/
```

The configured access and refresh token lifetimes are both 24 hours. Exact request and response fields are defined by the serializers and views in the app modules.

## API Overview

All paths below are prefixed with `/api/` unless stated otherwise.

| Area | Routes |
| --- | --- |
| Authentication | `/register/`, `/verify-email/`, `/login/` |
| Profile and password | `/profile/`, `/profile/update/`, `/change/password/`, `/forgot-password/`, `/reset-password/` |
| Doctors | `/doctors/`, `/doctors/<id>/` |
| Appointments | `/appointments/book/`, `/appointments/booked-slots/`, `/appointments/<id>/status/`, `/appointments/<id>/cancel/`, `/appointments/<id>/reschedule/`, `/patient/appointments/` |
| Appointment records and chat | `/appointments/<id>/record/`, `/appointments/<id>/chat/` |
| Payments | `/appointments/<id>/pay/`, `/appointments/<id>/confirm-payment/`, `/appointments/<id>/jazzcash-checkout-link/` |
| Documents and reviews | `/documents/`, `/documents/<id>/delete/`, `/upload/`, `/reviews/`, `/reviews/create/` |
| Doctor earnings | `/doctor/payout-method/`, `/doctor/payout-method/generate-link/`, `/doctor/payout-method/verify/`, `/doctor/earnings-analytics/`, `/doctor/wallet/withdraw/` |
| Admin API | `/admin/users/`, `/admin/overview/`, `/admin/appointments/<id>/`, `/admin/payments/<id>/decision/`, `/admin/comments/<id>/` |
| AI | `/ai/match-specialty/`, `/ai/summarize-report/` |
| Utilities | `/server-ip/`, `/call/reserve-slot/`, `/call/release-slot/` |

AI requests require authentication. The symptom matcher expects a `symptoms` field. Report summarization accepts either `file_id` or `file_url` and supports image files and text-based PDFs.

## WebSockets

The ASGI application exposes authenticated Channels routes:

```text
/ws/call/<appointment_id>/
/ws/notifications/<user_id>/
```

Use an ASGI server such as Daphne in deployment:

```powershell
daphne -b 0.0.0.0 -p 8000 med_backend.asgi:application
```

Configure Redis and set `DEBUG=False` for production channel layers.

## Payments

### Stripe

Stripe credentials are read from environment variables. Use the application payment and doctor payout endpoints rather than storing payment credentials in this backend.

### JazzCash

JazzCash uses a hosted HTTP POST checkout:

1. Request a signed checkout link from `/api/appointments/<id>/jazzcash-checkout-link/`.
2. Open the returned link and submit the Django checkout form.
3. JazzCash collects sensitive payment information on its hosted page.
4. JazzCash POSTs the result to `/pay/jazzcash/return/`.
5. The backend verifies the secure hash and requires `pp_ResponseCode == "000"` before marking payment successful and confirming the appointment.

Payment failures leave the appointment available for retry. Do not collect or store card numbers, CVV, OTPs, wallet PINs, or CNIC values in MedTag forms or logs.

See [JAZZCASH_INTEGRATION_CONTRACT.md](JAZZCASH_INTEGRATION_CONTRACT.md) for the complete state machine, callback rules, sandbox flow, and troubleshooting guidance.

## Testing

Run the Django test suite:

```powershell
python manage.py test
```

Run checks separately when diagnosing configuration issues:

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
```

## Production Checklist

- Set `DEBUG=False` and configure explicit `ALLOWED_HOSTS`.
- Replace the hardcoded Django `SECRET_KEY` with an environment-backed secret and rotate the existing key.
- Replace the hardcoded Gemini fallback in `ai/views.py` with a required environment variable before deployment.
- Use PostgreSQL and Redis; do not rely on the development in-memory channel layer.
- Configure HTTPS, secure cookies, CSRF trusted origins, and a restrictive CORS allowlist.
- Configure persistent object storage or a protected media volume for uploads.
- Keep `.env`, database files, media, logs, and credentials outside version control.
- Configure a public HTTPS `PUBLIC_BASE_URL` so JazzCash can reach the return callback.
- Run `python manage.py check --deploy` and review every warning.

## Related Documentation

- [JazzCash integration contract](JAZZCASH_INTEGRATION_CONTRACT.md)
- [JazzCash submission note](JAZZCASH_SUBMISSION_NOTE.md)
