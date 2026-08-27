# MedTag — JazzCash integration contract

Technical specification for the hosted-checkout (HTTP POST redirect) flow between **MedTag (Django)** and **JazzCash**. Suitable for design reviews, reports, and repository documentation.

**Submission-ready abstract:** [**`JAZZCASH_SUBMISSION_NOTE.md`**](./JAZZCASH_SUBMISSION_NOTE.md) — short summary for coursework reports or README snippets; this file remains the authoritative full contract.

---

## 1. Core principle

| Responsibility | Owner |
|----------------|--------|
| Sensitive payment inputs (card, OTP, CVV, wallet PIN, CNIC, etc.) | **JazzCash** (hosted pages only) |
| Initiating payment (signed request) | **Django** (`jazzcash_pay_start`) |
| Validating callback integrity and applying business rules | **Django** (`jazzcash_pay_return`) |

**MedTag does not validate or store payment credentials** (no full PAN/CVV in application storage). Outbound/inbound gateway fields may be logged redacted for auditing (e.g. password stripped in `GatewayTransactionLog`).

---

## 2. Payment flow (system behaviour)

### 2.1 Initiation — Django → JazzCash

1. User opens a **signed checkout URL** (from `GET /api/appointments/<id>/jazzcash-checkout-link/` with patient authentication).
2. Django renders **Pay Now**, which issues an **HTTP POST** to the JazzCash payment portal URL (`JAZZCASH_*_PAYMENT_POST_URL`).
3. Django creates a **`Payment`** row with `status = initiated` and a unique `merchant_txn_ref` (`pp_TxnRefNo`).

**Django explicitly does not:**

- validate card, OTP, CVV, or CNIC;
- capture or process funds;
- replace JazzCash’s authentication UI.

### 2.2 Processing — JazzCash (hosted)

User completes payment on **JazzCash sandbox or production** using their UI. Sandbox test data (cards, mobile, CNIC) is used **only on that hosted page**, not inside MedTag forms.

### 2.3 Callback — JazzCash → Django

JazzCash POSTs the result to **`pp_ReturnURL`**, handled by **`jazzcash_pay_return`** (CSRF exempt; external POST).

---

## 3. Callback validation (mandatory)

Both must hold for a **successful** booking update:

1. **Integrity:** HMAC / secure hash over returned fields is **valid** (Integrity Salt / shared secret as configured).
2. **Authorisation result:** `pp_ResponseCode == "000"` (success per JazzCash semantics).

Implementation: `success = hash_verified AND (pp_ResponseCode == "000")`.

**Incorrect pattern to avoid:** trusting a “success” flag or message without hash verification and explicit response code check.

---

## 4. Persistence rules

### 4.1 Success (hash OK **and** `pp_ResponseCode == "000"`)

| Entity | Update |
|--------|--------|
| `payments.Payment` | `status = succeeded` |
| `Appointment` | `payment_status = paid` |
| `Appointment` | `status = confirmed` |
| `Appointment` | `payment_id` set from transaction reference |

### 4.2 Failure (any other outcome)

| Entity | Update |
|--------|--------|
| `payments.Payment` | `status = failed` (with response code/message when present) |
| `Appointment` | **No change** to lifecycle/payment fields from this callback |

**Rationale:** the appointment remains a valid booking; the patient may **retry** payment. Payment failure does **not** auto-cancel the appointment.

Duplicate successful callbacks are treated idempotently where implemented (subsequent POSTs logged without resetting state).

---

## 5. State machine (correct model design)

### 5.1 `payments.Payment`

- **`initiated`:** Checkout prepared; user may be on JazzCash.
- **`succeeded`:** Terminal — callback validated as success.
- **`failed`:** Terminal — declined, error, hash failure, non-`000` code, or invalid callback.

There is **no** linear chain `initiated → succeeded → failed`; from `initiated` the outcome is **`succeeded` or `failed`**.

### 5.2 `Appointment`

- **`status`:** `confirmed` **only** after a **successful** JazzCash callback (per section 4.1).
- **`payment_status`:** set to **`paid`** on that same success path (MedTag shares this model with other flows such as Stripe where values include `unpaid`, `pending`, `paid`, `rejected`).
- Failures **do not** revert `Appointment.status` solely because payment failed — retry remains possible.

---

## 6. What MedTag implements (reference)

| Component | Purpose |
|-----------|---------|
| `payments.views.jazzcash_pay_start` | Build POST fields + `pp_SecureHash`, persist `Payment`, render Pay Now |
| `payments.views.jazzcash_pay_return` | Verify hash + code, update `Payment` / `Appointment` |
| `payments.services.jazzcash` | Secure hash construction / verification helpers |
| `payments.models.Payment` | Per-attempt gateway state |
| `payments.models.GatewayTransactionLog` | Audit trail for outbound/inbound payloads (sensitive fields redacted) |
| API: `GET …/appointments/<id>/jazzcash-checkout-link/` | Returns browser checkout URL |

Configuration: environment-driven (`JAZZCASH_MERCHANT_ID`, `JAZZCASH_MERCHANT_PASSWORD`, `JAZZCASH_INTEGRITY_SALT`, `PUBLIC_BASE_URL`, sandbox vs production URLs, `JAZZCASH_TEST_MODE`, etc.). See `med_backend/settings.py`.

---

## 7. Frontend / UX boundaries

| Location | Responsibility |
|----------|----------------|
| Django checkout template | **Pay Now**, optional sandbox help text (test PAN/CNIC are **hints** only) |
| JazzCash hosted pages | Actual entry of credentials and completion of payment |

---

## 8. Sandbox “API Call Log” and reporting

### 8.1 Three prerequisites (all must occur)

Merchant “API Call Log” / similar sandbox reports usually gain **meaningful rows only after all of**:

1. **Initiation reaches JazzCash from your app** — `jazzcash_pay_start` runs, user submits **Pay Now**, browser POSTs to JazzCash (not only opening Django or the merchant dashboard).  
2. **User completes payment on the JazzCash hosted page** — e.g. valid sandbox card/wallet submission; initiation alone is insufficient.  
3. **Gateway finalises and invokes your callback** — JazzCash POSTs to **`pp_ReturnURL`**; transaction is finalized from the portal’s reporting perspective once that path completes successfully.

If **any** prerequisite is missing, **“No Data Found”** is often **literally accurate** (“no completed row yet”), **not** proof of an application-wide failure.

### 8.2 What “No Data Found” commonly means

| Situation | Interpretation |
|-----------|----------------|
| Never clicked Pay Now / no POST to JazzCash | No initiation from app |
| Only opened sandbox dashboard | No transaction from your flow |
| Stopped mid-flow on JazzCash | Not a completed transaction |
| `pp_ReturnURL` unreachable (e.g. localhost), hash rejected, merchant blocked | Completion/callback chain never satisfied |

**Typical mistake:** Checking the sandbox log **before** running steps 1→3 once end-to-end, or assuming browser opened checkout page implies JazzCash logged a finalized transaction.

### 8.3 Smoke test sequence (verification)

1. Run Django (`jazzcash_pay_start` reachable).  
2. Open signed checkout URL; click **Pay Now** (confirm POST targets sandbox URL).  
3. Complete JazzCash sandbox payment (e.g. card `5123450000000008`, expiry `01/39`, CVV `100`, or sanctioned wallet sandbox values).  
4. Wait until the browser completes the **redirect / POST back** to your **Return URL** (`jazzcash_pay_return`).  
5. **Then** refresh JazzCash **API Call Log** (correct date filters and merchant account).

### 8.4 Expectation vs tools like Stripe

JazzCash sandbox reporting is **not** equivalent to Stripe’s dashboard: many views emphasize **completed** sandbox transactions rather than every intermediate or failed scrub. Rows often align with **`pp_ResponseCode`**, timestamps, reference numbers **after** a full successful path—not every “opened page” attempt.

### 8.5 MedTag-side verification

Regardless of sandbox UI latency, diagnose from MedTag :

- Django admin: **`GatewayTransactionLog`** (outbound vs inbound rows), **`Payment`** lifecycle.  
- Server logs around **`jazzcash_pay_return`**.

Always cross-check **`Payment`** and **`GatewayTransactionLog`** in MedTag admin plus server logs when debugging gateway visibility issues.

---

## 9. Versioning

Document reflects the integration as implemented in the MedTag Django `payments` app (hosted POST redirect + return URL callback). Align this document if JazzCash publishes breaking changes to fields, hash algorithms, or response semantics.
