# JazzCash Integration — Submission Note (Summary)

Paste this summary into coursework reports or a short README section. The full specification is in **`JAZZCASH_INTEGRATION_CONTRACT.md`**.

---

### Deliverable

| Item | Location |
|------|----------|
| Full integration contract | [`JAZZCASH_INTEGRATION_CONTRACT.md`](./JAZZCASH_INTEGRATION_CONTRACT.md) |
| Backend project root | `medtag-backend-main/medtag-backend-main/` |

---

### What the contract document covers

1. **Core principle** — JazzCash hosts sensitive payment steps; Django initiates and processes callbacks only.  
2. **End-to-end flow** — Initiation POST → JazzCash hosted UX → callback POST → verified persistence.  
3. **Callback rules** — Hash verification **and** `pp_ResponseCode == "000"` required before success-side updates.  
4. **Persistence** — Exactly which models/fields change on success vs failure.  
5. **State machines** — `Payment`: `initiated` → **`succeeded` or `failed`**. `Appointment`: **`confirmed`** and **`paid`** only on verified success; failure leaves booking unchanged for retry.  
6. **Implementation mapping** — Views, models, helpers, signed checkout API, env-driven settings.  
7. **UI/UX boundaries** — MedTag shows initiation; credentials only on JazzCash pages.  
8. **Sandbox / API logs** — Why dashboards may stay empty until a completed attempt (and callbacks) occur.  
9. **Format** — Versioned technical specification suitable for reviewers.

---

### Payment state machine (correct model)

```
initiated  →  succeeded   (verified hash + pp_ResponseCode "000")
         └→  failed       (anything else)
```

- **`initiated`** — Django created the outbound request and persisted `Payment` / logs.  
- **`succeeded`** — Callback passed integrity checks and success response code.  
- **`failed`** — Declined/error, invalid hash, non-success code, or invalid callback semantics.

---

### Appointment rule

| Event | Appointment change |
|--------|-------------------|
| Verified successful JazzCash callback | `payment_status = paid`, `status = confirmed`, `payment_id` set |
| Payment failure | **No automated rollback** — booking lifecycle fields unchanged; patient may retry |

**Design intent:** Avoid accidental cancellation of valid bookings; retries stay simple.

---

### Security posture

| Area | Behaviour |
|------|-----------|
| Card, OTP, CVV, CNIC, wallet PIN | Collected/processed **only by JazzCash** |
| Django | Validates **callback hash** + **response code**; builds signed initiation payloads |
| Storage | Payment credentials not stored as application-owned secrets; gateway logs redact passwords |

---

### Flow summary

```
User opens signed checkout URL (Django)
    → Django POST initiates JazzCash checkout
User completes payment on JazzCash (hosted only)
    → JazzCash POST callback to Django
Django verifies hash + response code
    → Updates Payment (+ Appointment only if success)
```

---

### JazzCash sandbox “API Call Log” — why it can stay empty

The merchant **API Call Log** (and similar sandbox reports) normally reflects activity only when **all three** steps complete:

| # | Required event |
|---|----------------|
| **1** | **App sends initiation** — `jazzcash_pay_start` renders checkout; user clicks **Pay Now**; browser **POST** goes to JazzCash (not browsing Django or the JazzCash homepage alone). |
| **2** | **User finishes payment on JazzCash** — test card/mobile/CNIC submitted; flow completes on JazzCash-hosted UI. |
| **3** | **Gateway finalizes + reaches your callback** — JazzCash **POST** to **`pp_ReturnURL`**; transaction recorded as finalized for reporting. |

Missing **any** step → dashboards often remain **empty** (“No Data Found” = usually **no completed transaction yet**, not necessarily a bug).

| Typical gap | Meaning |
|----------------|---------|
| No Pay Now / no outbound POST | No request from your integration |
| Dashboard opened only | Your flow hasn’t executed |
| Checkout abandoned mid-page | Incomplete attempt |
| Return URL unreachable, hash rejection, sandbox config | Completion/callback chain not satisfied |

**Minimal end-to-end test:** (1) run Django → (2) open signed checkout URL and Post to JazzCash → (3) pay with sanctioned sandbox PAN (e.g. `5123450000000008` / `01/39` / `100`) → (4) wait for **return** to `jazzcash_pay_return` → (5) **then** reload API Call Log (correct merchant + date range).

**Compared to Stripe:** JazzCash sandbox logs often emphasize **completed** sandbox transactions—not every tentative or purely local state.

**Truth on MedTag:** Inspect **`Payment`** and **`GatewayTransactionLog`** in admin and Django logs (`jazzcash_pay_return`). If Django shows inbound logs with **`pp_ResponseCode`** `000` and hash OK, initiation + callback succeeded even if JazzCash UI lags.

---

### Implementation traceability (code)

| Spec concept | Django implementation |
|--------------|-------------------------|
| Initiation | `payments.views.jazzcash_pay_start` |
| Callback | `payments.views.jazzcash_pay_return` |
| Transaction lifecycle | `payments.models.Payment` |
| Booking updates | `accounts.models.Appointment` (only on validated success path) |
| Checkout URL for SPA | `GET /api/appointments/<id>/jazzcash-checkout-link/` |

For field-level rules and diagrams, open **`JAZZCASH_INTEGRATION_CONTRACT.md`**.
