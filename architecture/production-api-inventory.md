# Clippit production API inventory and gap register

Last audited: 2026-09-21

This document is the backend contract for taking Clippit from the current reviewable product to a production service for creators, brands, support staff, finance operators, trust and safety, and administrators.

It has four jobs:

1. Record every endpoint currently mounted by `backend/main.py`.
2. Distinguish code that exists from code that is genuinely launch-ready.
3. Define the endpoints still missing from the customer and operator journeys.
4. Identify production work that cannot be solved by adding an endpoint.

The inventory was produced from the FastAPI routers and FastAPI's automatically mounted documentation routes, not from the older README count. There are currently **101 mounted routes** in the main application: 97 application routes plus 4 framework documentation routes. This count includes hidden webhook/media routes and internal service routes.

The audited target adds **194 definite routes**: **123 P0 launch blockers** and **71 P1 broad-production routes**. It also defines **21 conditional routes** used only when help/legal content is managed internally or when domains run as separate services/workers. That produces a maximum target surface of **316 main-application routes**. The repository also contains 38 unmounted provider-experiment routes documented separately and excluded from that total. This does not mean 215 unrelated systems need to be written: many of the new routes are thin, permissioned views or actions over shared onboarding, session, identity, campaign-draft, asset, ledger, support, dispute, verification, moderation, and operator services.

## Status and priority

| Label | Meaning |
|---|---|
| Built | The route and domain behavior exist in the repository. It still needs frontend integration and deployment verification. |
| Built, dependency pending | The route exists, but a provider or production subsystem behind it is incomplete or still defaults to a sandbox/local implementation. |
| Internal | Service-to-service or operator-only route; never call it directly from the browser. |
| Missing P0 | Required before real customers or real money are allowed onto the service. |
| Missing P1 | Required before a broad public launch or a staffed production operation. |
| Conditional | Required only if the named concern is split into a separate service. |

P0 means launch-blocking. P1 does not mean decorative or optional; it means the product can be piloted without it only if the team has an explicit manual operating procedure.

## Production-wide API rules

These rules apply to every route, including routes already built.

- Keep the existing paths for the first integration pass. Add `/api/v1` at the gateway or in one coordinated migration; do not version routes piecemeal.
- Browser routes use short-lived bearer access tokens plus rotating refresh tokens in secure, HTTP-only, `SameSite=Lax` cookies.
- Internal routes require `X-Internal-Secret` now and service identity/mTLS when services are separated.
- Every list route uses cursor pagination, a bounded `limit`, deterministic ordering, and documented filters.
- Every money-moving POST accepts an `Idempotency-Key` and returns the same resource for safe retries.
- Every mutation writes an audit event containing actor, subject, resource, request ID, timestamp, and safe metadata.
- Errors use one envelope: `code`, `message`, `field_errors`, `request_id`, and optional `retry_after`.
- Timestamps are ISO 8601 UTC. Money is serialized as decimal strings plus an ISO currency code; never use binary floats.
- Public and browser responses never expose access tokens, unmasked bank details, internal trust features, provider secrets, or raw storage keys.
- Webhooks verify signatures against the raw request body, store provider event IDs, and are idempotent.
- All upload/download routes enforce ownership, MIME sniffing, size limits, malware scanning, expiry, and signed access.
- Destructive actions use re-authentication and a confirmation token when they affect identity, payout destinations, campaign money, or account deletion.

---

# Part I: endpoints that already exist

## System and framework-mounted documentation

| Method and path | Access | What it does | Status |
|---|---|---|---|
| `GET /health` | Public | Returns a shallow process-health response. It does not prove database, storage, provider, queue, or worker readiness. | Built |
| `GET /openapi.json` | Public by FastAPI default | Returns the generated OpenAPI schema for routes included in the schema. Hidden webhook/media routes are omitted. | Built automatically; disable publicly or protect in production |
| `GET /docs` | Public by FastAPI default | Serves Swagger UI. | Built automatically; disable publicly or protect in production |
| `GET /docs/oauth2-redirect` | Public by FastAPI default | Swagger UI OAuth redirect helper. | Built automatically; disable with Swagger or protect in production |
| `GET /redoc` | Public by FastAPI default | Serves ReDoc. | Built automatically; disable publicly or protect in production |

## Authentication and email recovery

| Method and path | Access | Request / result | Status |
|---|---|---|---|
| `POST /auth/signup` | Public, rate limited | Creates a creator or organisation account from email, password, name, and role; returns a bearer token and user. | Built |
| `POST /auth/login` | Public, rate limited | Validates email/password and returns a bearer token and user. | Built |
| `POST /auth/logout` | Signed in | Revokes the current access-token `jti`. Other devices remain signed in. | Built |
| `GET /auth/me` | Signed in | Returns the current user, role, email-verification state, and onboarding state. | Built |
| `POST /auth/verify-email` | User/email flow | Consumes the six-digit email code and marks the address verified. | Built, dependency pending: production email delivery |
| `POST /auth/verify-email/resend` | User/email flow, cooldown | Sends a replacement verification code without bypassing cooldown/attempt limits. | Built, dependency pending: production email delivery |
| `POST /auth/forgot-password` | Public, enumeration safe | Starts password recovery and always returns a neutral accepted response. | Built, dependency pending: production email delivery |
| `POST /auth/recovery-code/verify` | Public, attempt limited | Validates a recovery code and returns a single-use reset token. | Built |
| `POST /auth/reset-password` | Reset-token flow | Replaces the password and invalidates existing sessions/tokens. | Built |
| `POST /auth/refresh` | Refresh-token flow | Rotates a refresh token; reuse of an already-spent one revokes the whole session. | Built 2026-09-22 |
| `GET /auth/sessions` | Signed in | Lists this account's active sessions/devices, marking the current one. | Built 2026-09-22 |
| `DELETE /auth/sessions/{session_id}` | Signed in, owner | Revokes one session immediately (its access tokens stop working, not just its refresh token). | Built 2026-09-22 |
| `DELETE /auth/sessions/others` | Signed in | Revokes every session but the caller's own. | Built 2026-09-22 |
| `POST /auth/change-password` | Signed in | Requires the current password; revokes other sessions by default. | Built 2026-09-22 |
| `POST /auth/password` | Signed in, step-up | Sets a first password for a Google-only account. | Built 2026-09-22 |
| `GET /auth/providers` | Signed in | Which sign-in methods are linked and which are safe to remove. | Built 2026-09-22 |
| `DELETE /auth/providers/google` | Signed in, step-up | Unlinks Google — refused if no password exists to fall back to. | Built 2026-09-22 |
| `POST /auth/step-up/request`, `POST /auth/step-up/verify` | Signed in | Generic action-bound re-authentication proof (password only — the only factor that exists). Built as a primitive; not yet required by the endpoints that should ask for it (payout destination, refunds, email change). | Built 2026-09-22 |
| `DELETE /auth/account` | Signed in, step-up | Anonymises the account (email/name scrubbed, socials disconnected, every session revoked); refuses while money traces back to it unsettled. | Built 2026-09-22 |
| `GET /auth/google/login`, `GET /auth/google/callback` | Public / OAuth callback | Google OIDC sign-in — creates, signs in to, or (email-verified match only) auto-links an account. Verifies via Google's `tokeninfo` endpoint, not local JWKS. | Built 2026-09-22, dependency pending: real `GOOGLE_CLIENT_ID`/`SECRET`, never exercised against real Google |
| `GET /auth/google/link` | Signed in | Attaches Google to the current account (a redirect flow, not the `POST .../link` the inventory names — see the note in Part II §B). | Built 2026-09-22 |

## Connected social accounts

| Method and path | Access | Request / result | Status |
|---|---|---|---|
| `GET /social/accounts` | Signed in | Lists the caller's connected platform accounts. | Built |
| `DELETE /social/{platform}` | Signed in, owner | Disconnects one social account. | Built |
| `GET /social/{platform}/login` | Signed in via query token, OAuth state protected | Starts the selected platform OAuth flow. | Built, dependency pending: provider production approval and token-refresh policy |
| `GET /social/{platform}/callback` | OAuth callback | Validates state, exchanges the code, reads the platform profile where possible, stores tokens, and redirects to the frontend. | Built, dependency pending: provider production approval and token-refresh policy |

The generic social paths are mounted for all platform strings, but that does not mean every platform works. TikTok, Instagram, Facebook, Threads, and X adapters exist. YouTube is only an enum value and still needs a provider, OAuth scopes, token lifecycle, ingestion adapter, and tests.

## Shared profile and preferences

| Method and path | Access | Request / result | Status |
|---|---|---|---|
| `GET /profile` | Signed in | Returns the account, connected socials, and preferences in one payload. | Built |
| `GET /profile/preferences` | Signed in | Returns notification and account preferences. | Built |
| `PATCH /profile/preferences` | Signed in | Partially updates supported preferences. | Built |

## Onboarding: current aggregate completion routes

These are the only two onboarding routes currently implemented. They accept a final aggregate payload; they do not support step-by-step autosave, cross-device resume, draft reset, explicit completion, or the complete set of answers collected by the frontend.

| Method and path | Access | Request / result | Status |
|---|---|---|---|
| `PUT /creators/me/onboarding` | Creator | Stores one final creator onboarding payload and marks onboarding complete. | Built, schema incomplete |
| `PUT /organisations/me/onboarding` | Organisation | Stores one final organisation onboarding payload and marks onboarding complete. | Built, schema incomplete |

The current creator body only supports `display_name`, one combined `interests` list, `platforms`, optional `photo_upload_id`, `discovery_source`, `experience`, and `goals`. It cannot preserve location or distinguish content the creator makes from content the creator watches.

The current organisation body only supports `name`, `bio`, optional `photo_upload_id`, `production_workflow`, `team_size`, `campaign_goal`, and `budget_range`. It cannot preserve the person's preferred name separately from the organisation, location, brand-versus-individual identity, company-registration answer, website during onboarding, content-to-fund lanes, content-to-view lanes, or discovery source.

## Creator profile, onboarding, bank destination, and workspace

| Method and path | Access | Request / result | Status |
|---|---|---|---|
| `PUT /creators/me/bank-details` | Creator | Saves bank code/name/account number and resets verification whenever details are submitted. | Built |
| `GET /creators/me/bank-details` | Creator | Returns the creator's masked payout destination and verification state. | Built |
| `GET /creators/{creator_id}/bank-details` | Admin only | Returns a creator's masked bank details for a support/dispute case. | Built; keep admin-only and audit every read before launch |
| `GET /creators/me/profile` | Creator | Returns editable creator identity, bio, photo, interests, intended platforms, discovery source, experience, goals, and onboarding state. | Built |
| `PUT /creators/me/profile` | Creator | Replaces editable creator profile fields after ownership-checking the photo upload. | Built |
| `GET /creators/me/clips` | Creator | Returns creator submission totals and clip rows with status, verified views, and earnings. | Built |
| `GET /creators/me/accounts` | Creator | Returns every supported platform, connection state, handle, and last reading time. | Built, dependency pending for YouTube |
| `GET /creators/me/overview` | Creator | Returns dashboard campaign recommendations and earnings summary. | Built |

## Organisation profile and onboarding

| Method and path | Access | Request / result | Status |
|---|---|---|---|
| `GET /organisations/me/profile` | Organisation | Returns organisation identity, description, logo, finance contact, workflow data, and verification state. | Built |
| `PUT /organisations/me/profile` | Organisation | Updates editable organisation fields; business verification itself remains admin-controlled. | Built |

## Campaign discovery and management

| Method and path | Access | Request / result | Status |
|---|---|---|---|
| `POST /campaigns` | Verified organisation | Creates a draft campaign with identity, brief fields, platforms, budget/rate/duration data, rules, and cover. | Built |
| `GET /campaigns` | Signed in; visibility is role/status aware | Lists public live campaigns for creators or the organisation's own campaigns. Supports search/feed/category/platform/status and pagination fields. | Built |
| `GET /campaigns/{campaign_ref}` | Signed in/public according to status | Returns one campaign by UUID or slug; draft visibility is restricted to owner/admin. | Built |
| `GET /campaigns/{campaign_ref}/pool` | Permitted campaign viewer | Returns promised, allocated, and remaining pot values. | Built |
| `PATCH /campaigns/{campaign_ref}` | Owning organisation/admin; draft only | Edits mutable draft campaign fields. | Built |
| `PUT /campaigns/{campaign_ref}/payout-rule` | Owning organisation/admin; draft only | Replaces rate, minimum views, creator cap, and related payout rules. | Built |
| `GET /campaigns/{campaign_ref}/rules` | Permitted campaign viewer | Lists must-do and must-avoid checklist requirements. | Built |
| `PUT /campaigns/{campaign_ref}/rules` | Owning organisation/admin; draft only | Replaces the complete ordered requirements checklist. | Built |
| `POST /campaigns/{campaign_ref}/activate` | Owning organisation/admin | Activates only after confirmed full funding. | Built |
| `POST /campaigns/{campaign_ref}/pause` | Owning organisation/admin | Stops new entries while existing approved clips continue under the documented rule. | Built |
| `POST /campaigns/{campaign_ref}/resume` | Owning organisation/admin | Reopens entries for a paused live campaign. | Built |
| `POST /campaigns/{campaign_ref}/close` | Owning organisation/admin | Books final eligible views, closes the campaign, and stops tracking. | Built |
| `GET /campaigns/{campaign_ref}/stats` | Owning organisation/admin | Returns live pot, view deltas, pipeline counts, and last-read signals. | Built |
| `GET /campaigns/{campaign_ref}/submissions` | Owning organisation/admin | Lists recent campaign submissions and their current earning/review state. | Built |
| `GET /campaigns/{campaign_ref}/report` | Owning organisation/admin | Downloads the campaign report as CSV. | Built |

## Funding

| Method and path | Access | Request / result | Status |
|---|---|---|---|
| `POST /campaigns/{campaign_ref}/funding` | Owning organisation | Creates or returns the open funding order, locks campaign terms, and returns a hosted checkout URL or collection account. | Built, dependency pending: production Paystack verification |
| `GET /campaigns/{campaign_ref}/funding` | Owning organisation/admin | Returns the latest funding order and status. | Built, dependency pending: production Paystack verification |
| `POST /campaigns/{campaign_ref}/funding/confirm` | Owning organisation | Asks the provider whether funds actually cleared; the customer's click alone cannot open the campaign. | Built, dependency pending: production Paystack verification |
| `DELETE /campaigns/{campaign_ref}/funding` | Owning organisation | Cancels an unpaid order and unlocks the draft; refuses after payment is claimed. | Built, dependency pending: production Paystack verification |

## Brand workspace and review queue

| Method and path | Access | Request / result | Status |
|---|---|---|---|
| `GET /brand/overview` | Organisation | Returns dashboard counts, spend, recent view/earning movement, and the featured live campaign. | Built |
| `GET /brand/reviews` | Organisation/admin | Returns needs-review, appeal, or resolved queue data and tab counts. | Built |
| `GET /brand/reviews/{submission_id}` | Campaign owner/admin | Returns clip evidence, requirement results, confidence, and appeal context. | Built |
| `POST /brand/reviews/{submission_id}/approve` | Campaign owner/admin | Approves the submission and allows eligible verified views to earn. | Built |
| `POST /brand/reviews/{submission_id}/request-correction` | Campaign owner/admin | Records a reason/requirement and sends the creator a correction verdict. | Built |

## Creator submissions, verdicts, appeals, and performance

| Method and path | Access | Request / result | Status |
|---|---|---|---|
| `POST /submissions` | Verified creator | Registers a public post and optional owned original-video upload after campaign/account/platform checks. | Built, dependency pending: automated brief verifier |
| `GET /submissions` | Signed in, role-scoped | Lists submissions visible to the caller. | Built |
| `GET /submissions/{submission_id}` | Creator owner, campaign owner, or admin | Returns status, verification steps, requirement verdicts, rejection reason, and appeal. | Built |
| `POST /submissions/{submission_id}/withdraw` | Creator owner | Withdraws an eligible submission and stops its tracking. | Built |
| `POST /submissions/{submission_id}/appeal` | Creator owner | Creates one appeal with a minimum-length reason and optional owned evidence upload. | Built |
| `GET /submissions/{submission_id}/earnings` | Authorised participant/admin | Returns accrued/payable earnings and next release date for the clip. | Built |
| `GET /submissions/{submission_id}/performance` | Authorised participant/admin | Returns normalized platform performance and trust-safe public details. | Built |

The default verifier currently routes submissions with requirements to human review. A real frame/transcript/brief verifier is still missing even though the endpoint exists.

## Earnings and leaderboard

| Method and path | Access | Request / result | Status |
|---|---|---|---|
| `GET /earnings/summary` | Creator | Returns payable, on-hold, processing, paid, lifetime views, and next-clear data. | Built |
| `GET /earnings/history` | Creator | Returns accrual ledger entries with campaign, clip, billable views, amount, and state. | Built |
| `GET /leaderboard` | Signed in | Returns weekly/all-time or campaign-filtered verified-view rankings plus the caller's rank. | Built |

## Banks, payouts, and payment webhook

| Method and path | Access | Request / result | Status |
|---|---|---|---|
| `GET /banks` | Signed in | Returns supported Nigerian banks from the active payment provider. | Built, dependency pending: production provider |
| `POST /banks/resolve` | Creator | Resolves a bank code/account number to an account name. | Built, dependency pending: production provider |
| `POST /creators/me/bank-details/verify` | Creator | Confirms that the saved destination resolves and marks it verified. | Built, dependency pending: production provider |
| `POST /payouts` | Verified creator, idempotent request body | Reserves eligible earnings and dispatches a transfer. | Built, dependency pending: live money rehearsal and provider reconciliation |
| `GET /payouts` | Creator | Lists the creator's payouts. | Built |
| `GET /payouts/{payout_id}` | Creator owner/admin | Returns status, destination, provider reference, allocations, and provenance used by the receipt. | Built |
| `POST /webhooks/payments` | Signed provider webhook, hidden from schema | Applies funding and transfer events idempotently after raw-body signature verification. | Built, dependency pending: live provider webhook verification |

## Notifications

| Method and path | Access | Request / result | Status |
|---|---|---|---|
| `GET /notifications` | Signed in | Returns the caller's notification inbox and unread information. | Built |
| `POST /notifications/read-all` | Signed in | Marks every notification read. | Built |
| `POST /notifications/{notification_id}/read` | Notification owner | Marks one notification read. | Built |

## Uploads and development media serving

| Method and path | Access | Request / result | Status |
|---|---|---|---|
| `POST /uploads/images` | Signed in, rate limited | Streams a profile photo, logo, or campaign cover into the active storage adapter. | Built, dependency pending: R2, scanning, signed delivery |
| `POST /uploads/videos` | Verified user, rate limited | Streams an original submission video. | Built, dependency pending: R2, multipart upload, scanning, thumbnail/transcode |
| `POST /uploads/evidence` | Signed in, rate limited | Streams appeal evidence. | Built, dependency pending: R2, scanning, signed delivery |
| `GET /media/{key:path}` | Possession of unguessable local URL; hidden from schema | Serves local development files. It must not be the production delivery mechanism. | Built for development only |

## Admin and finance operations

All routes in this section require the admin role. Every mutation is intended to be auditable.

| Method and path | Request / result | Status |
|---|---|---|
| `GET /admin/overview` | Returns user/campaign/payout counts, review and appeal counts, liability, unconfirmed funding, and blocked earnings. | Built |
| `GET /admin/payouts` | Lists/filter payouts with creator and provider data. | Built |
| `POST /admin/payouts/{payout_id}/retry` | Safely re-drives a pending/processing payout using the provider idempotency reference. | Built, dependency pending: live provider reconciliation |
| `POST /admin/payouts/{payout_id}/fail` | Marks an in-flight payout failed with a reason and releases its allocation. | Built |
| `GET /admin/funding` | Lists/filter funding orders. | Built |
| `POST /admin/funding/{order_id}/confirm` | Manually confirms fully received funding with amount and audit note. | Built |
| `GET /admin/earnings/blocked` | Lists earning accounts blocked by trust, cap, or pot conditions. | Built |
| `POST /admin/earnings/settle` | Runs one settlement tick immediately. | Built |
| `POST /admin/campaigns/sweep` | Runs one campaign expiry/close sweep immediately. | Built |
| `POST /admin/organisations/{user_id}/verify-business` | Sets or removes business verification and legal name. | Built, but there is no customer application or admin queue yet |
| `GET /admin/audit` | Reads filtered recent audit events. | Built |

## Internal auth and intelligence

These routes are implementation contracts, not browser APIs.

| Method and path | Caller / result | Status |
|---|---|---|
| `GET /internal/users/{user_id}` | Other backend modules resolve role and identity through the internal contract. | Internal |
| `GET /internal/social-accounts/{user_id}/{platform}/token` | Intelligence retrieves a current platform token. | Internal; token refresh remains incomplete for Meta providers |
| `POST /internal/submissions/{submission_id}/metrics` | Registers content or forces a fresh platform reading. | Internal, dependency pending for YouTube |
| `GET /internal/submissions/{submission_id}/performance` | Reads stored normalized performance without calling the platform. | Internal |
| `GET /internal/submissions/{submission_id}/trust` | Returns the latest trust verdict. | Internal |
| `POST /internal/submissions/{submission_id}/trust/review` | Stores a human trust label. | Internal |
| `GET /internal/trust/rules` | Returns the currently configured trust thresholds. | Internal |
| `POST /internal/submissions/{submission_id}/tracking/stop` | Stops scheduled metric tracking. | Internal |
| `POST /internal/submissions/{submission_id}/tracking/resume` | Resumes scheduled metric tracking. | Internal |

---

# Part II: endpoints still required

## A. Service health and production operations

| Priority | Method and path | Required contract |
|---|---|---|
| Missing P0 | `GET /ready` | Readiness check for database migrations/connectivity, storage, queue/worker lease, and required provider configuration. Return non-200 when traffic must not be sent to the instance. |
| Missing P1 | `GET /version` | Return release SHA, build time, API version, and migration head without exposing secrets. |
| Missing P0 | `GET /internal/metrics` | Authenticated Prometheus-compatible counters/histograms for HTTP, jobs, platform reads, verification, funding, settlement, and payouts. Never expose publicly. |

`GET /health` can remain the liveness check; it should stay cheap and must not call dependencies.

## B. Sessions, password/security settings, Google auth, and account lifecycle

These endpoints are required by the existing Google buttons and security/device UI. Current JWT revocation only logs out the current token and cannot model real device sessions.

| Priority | Method and path | Required contract |
|---|---|---|
| Missing P0 | `POST /auth/refresh` | Rotate a refresh token, revoke the previous token family member, detect reuse, and return a new short-lived access token. |
| Missing P0 | `POST /auth/change-password` | Require current password or recent step-up authentication, set the new password, and optionally revoke other sessions. |
| Missing P0 | `GET /auth/sessions` | List the caller's sessions with ID, device/browser label, approximate location, created time, last-seen time, and current-session marker. |
| Missing P0 | `DELETE /auth/sessions/{session_id}` | Revoke one owned session. Prevent deleting another user's session. |
| Missing P0 | `DELETE /auth/sessions/others` | Revoke every session except the current one. |
| Missing P0 | `GET /auth/google/login` | Start Google OIDC with state, nonce, PKCE, and the intended creator/organisation role when signing up. |
| Missing P0 | `GET /auth/google/callback` | Validate OIDC claims, safely link or create the account, prevent account takeover through ambiguous emails, and establish a session. |
| Missing P0 | `GET /auth/providers` | Return the caller's usable sign-in methods, password-present state, linked provider identities, and whether each method may be removed safely. |
| Missing P1 | `POST /auth/providers/google/link` | Start/complete an authenticated Google-link flow with step-up verification and collision protection. This may share the OIDC callback internally but needs an explicit link intent. |
| Missing P0 | `DELETE /auth/providers/google` | Unlink Google only when another verified sign-in method remains; require recent step-up and audit the change. |
| Missing P0 | `POST /auth/password` | Let a provider-only account establish its first password after recent provider authentication; distinct from changing an existing password. |
| Missing P1 | `POST /auth/2fa/setup` | Create a pending TOTP secret and return an `otpauth` URI/QR payload without enabling 2FA yet. |
| Missing P1 | `POST /auth/2fa/confirm` | Verify the first TOTP, enable 2FA, and return one-time recovery codes. |
| Missing P1 | `POST /auth/2fa/challenge` | Complete a login or sensitive-action challenge with TOTP or one recovery code. |
| Missing P1 | `DELETE /auth/2fa` | Disable 2FA after password/recent step-up verification. |
| Missing P1 | `POST /auth/2fa/recovery-codes/regenerate` | Invalidate old recovery codes and issue a new one-time set after step-up verification. |
| Missing P1 | `POST /auth/email-change/request` | Verify the password/step-up state and send codes to old and new addresses. |
| Missing P1 | `POST /auth/email-change/confirm` | Consume both proofs, change the email, audit the change, and notify the old address. |
| Missing P0 | `POST /auth/step-up/request` | Start a short-lived sensitive-action challenge using the strongest available verified factor; bind it to a declared action such as payout-destination change, refund, email change, or account deletion. |
| Missing P0 | `POST /auth/step-up/verify` | Verify password/TOTP/email code as policy allows and return a single-action, short-expiry proof token. Never return a general long-lived access token. |
| Missing P1 | `POST /auth/account-export` | Queue a privacy export containing profile, campaigns/submissions, ledger, and audit-visible customer data; return a job ID. |
| Missing P0 | `DELETE /auth/account` | Re-authenticate, apply legal/ledger retention rules, revoke sessions/tokens, disconnect socials, and schedule deletion/anonymisation. Refuse unsafe deletion while money is unsettled. |
| Missing P1 | `GET /auth/account-export/{job_id}` | Return export status and a short-lived download URL when ready. |

**2026-09-22 — Built**, all P0 rows above except the 2FA/email-change P1 rows (still missing, along with account-export):
- `POST /auth/refresh`, `GET/DELETE /auth/sessions*`: a new `sessions`/`refresh_tokens` pair backs real, revocable devices. Access tokens now carry a `sid` claim checked on every request; revoking a session invalidates its access tokens immediately, not just its refresh token. Refresh-token reuse (a token presented twice) revokes the whole session — signup/login now return a `refresh_token` alongside `access_token`.
- `POST /auth/change-password`, `POST /auth/password` (first password for a Google-only account), `GET /auth/providers`, `DELETE /auth/providers/google`: `users` gained `has_password`/`google_id`/`google_email`; `/auth/providers` reports which method is safe to remove (never the last one).
- `POST /auth/step-up/{request,verify}`: a generic, action-bound proof primitive (password only today — the only factor that exists; 2FA would add a factor choice at `request` without changing the shape). **Not yet wired to the endpoints that should require it** — payout-destination change, refunds, email change — those still accept the request without a step-up token. `DELETE /auth/account` and `POST /auth/password`/`DELETE /auth/providers/google` do require and consume one.
- `GET /auth/google/login`, `GET /auth/google/callback`: real OIDC (state+nonce, verified via Google's `tokeninfo` endpoint rather than local JWKS/RS256 — this environment has no `cryptography` wheel; see `modules/auth/google.py`'s docstring). Auto-links onto an existing account only when Google reports the email verified; an unverified match or one already linked to a different Google account is refused, not silently taken over or duplicated. **Needs a real `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`** (both empty by default; `/auth/google/login` 503s without them) — never exercised against real Google.
- `POST /auth/providers/google/link` is built as `GET /auth/google/link` instead (a redirect-flow login, matching how `/social/{platform}/login` already works) rather than a POST — the doc's path assumed a JSON call, but starting an OAuth round trip needs a browser navigation either way.
- PKCE was scoped out of the Google flow: Google's server-side (confidential-client) OAuth flow doesn't require it the way TikTok's public-client PKCE flow does; the state token still carries a nonce, which is what OIDC actually needs checked back against the id_token.

## C. Onboarding lifecycle: creator and brand

Onboarding is a first-class product domain. Authentication already determines whether the account is a creator or an organisation; onboarding must never ask the user to choose that account role again. An organisation account may still branch between an individual funder and a brand/business because those paths collect different data.

The two existing `PUT .../onboarding` routes are final-submit endpoints, not a complete lifecycle. Production onboarding must autosave after every screen, resume on another device, preserve conditional branches, validate completion on the server, and redirect from the authenticated user state rather than browser `localStorage`.

### Required onboarding endpoints

| Priority | Method and path | Required contract |
|---|---|---|
| Missing P1 | `GET /onboarding/options` | Return a versioned catalogue of content categories, publishing platforms, experience levels, discovery sources, goals, team sizes, workflows, and budget ranges. Include enabled/disabled state and display order so backend validation and frontend choices cannot drift. |
| Missing P0 | `GET /creators/me/onboarding` | Return creator onboarding status and saved draft: `not_started`, `in_progress`, or `completed`; schema version; current step; completed/required steps; percentage; answer payload; validation blockers; and `updated_at`. |
| Missing P0 | `PATCH /creators/me/onboarding` | Autosave any valid subset of creator answers after one screen. Accept an optimistic revision/version and `last_step`; return the canonical saved draft and next required step. It must not mark onboarding complete. |
| Missing P0 | `POST /creators/me/onboarding/complete` | Validate every compulsory creator answer together, atomically copy the final identity/feed fields into the creator profile, set `onboarding_completed`, emit an audit/analytics event, and return `next_route: /dashboard`. Idempotent after completion. |
| Missing P0 | `DELETE /creators/me/onboarding/draft` | Reset an incomplete creator draft. It must not delete the account, uploaded photo, profile, or a completed onboarding record. |
| Missing P0 | `GET /organisations/me/onboarding` | Return organisation onboarding status, saved draft, selected individual/business branch, calculated required steps, validation blockers, completion percentage, and revision. |
| Missing P0 | `PATCH /organisations/me/onboarding` | Autosave any valid subset of organisation answers, recalculate the conditional step graph, clear answers made invalid by an intentional branch change, and return the canonical next step. It must not mark onboarding complete. |
| Missing P0 | `POST /organisations/me/onboarding/complete` | Validate the appropriate individual or business branch, update the organisation/funder profile atomically, set `onboarding_completed`, create the verification state where applicable, and return `next_route: /brand`. Idempotent after completion. |
| Missing P0 | `DELETE /organisations/me/onboarding/draft` | Reset an incomplete organisation draft without deleting the account, profile, uploaded image, or completed record. |

**2026-09-22 — Built** (all eight `GET`/`PATCH`/`.../complete`/`.../draft` rows above, both creator and organisation): answers autosave into a JSONB draft on the existing profile row, guarded by `revision` for the two-tabs case; `complete` re-validates the accumulated draft against the same schema the old `PUT` used and is idempotent once `onboarding_completed`; `DELETE .../draft` refuses once complete. Still missing from this pass: `GET /onboarding/options` (the versioned catalogue — answers are still validated against hand-coded bounds, not a driven list), the organisation individual/business branch recalculation, `next_route`/analytics-event on completion, and the wider creator/organisation field contract below (location, makes/watches split, funder identity) — the draft still only carries the original `PUT` schemas' fields.

The existing `PUT /creators/me/onboarding` and `PUT /organisations/me/onboarding` may temporarily remain as backwards-compatible all-at-once completion calls. New frontend work should use GET/PATCH/complete so a phone refresh or connection loss never destroys progress. Remove or deprecate the PUT routes only in a versioned API change.

### Creator onboarding field contract

| Step key | API field | Type and validation | Required |
|---|---|---|---|
| `name` | `display_name` | Trimmed string, 2-80 characters. | Yes |
| `photo` | `photo_upload_id` | Owned image upload UUID or null. The existing `POST /uploads/images` performs the upload. | No; skipping must be explicit and valid |
| `location` | `location` | Structured object with `country_code`, optional `state`, and `city`; Nigeria is the only payout country in v1. | Yes |
| `makes` | `makes_content_categories` | 2-5 unique versioned category keys. | Yes |
| `watches` | `watches_content_categories` | 2-5 unique versioned category keys, stored separately from `makes`. | Yes |
| `platforms` | `publishing_platforms` | At least one supported platform key. Choosing YouTube is allowed as an interest only if the response clearly states whether connection is currently available. | Yes |
| `experience` | `experience_level` | One versioned option key. | Yes |
| `discovery` | `discovery_source` | One versioned option key plus optional bounded free text for `other`. | Yes |
| `goal` | `primary_goal` | One versioned creator-goal key. | Yes |

The completed creator response must include the normalized creator profile, role, completion timestamp, destination route, and any next action such as connecting a selected platform. Do not store these answers only in generic JSON if they drive campaign matching; queryable fields or normalized association tables are required.

### Brand/individual onboarding field contract

| Step key | API field | Type and validation | Individual funder | Brand/business |
|---|---|---|---|---|
| `name` | `preferred_name` | Trimmed string, 2-80 characters; this is the person using the workspace. | Required | Required |
| `photo` | `photo_upload_id` | Owned image UUID or null, uploaded through `POST /uploads/images`. | Optional | Optional |
| `location` | `location` | Structured `country_code`, optional `state`, and `city`. | Required | Required |
| `identity` | `funder_type` | `individual` or `business`. This is not the auth role. | Required | Required |
| `registration` | `company_registered` | Boolean. Omit for an individual. | Not applicable | Required |
| `organisation` | `organisation_name` | Public name creators will see. | Not applicable | Required when the company is registered; collect a working name when unregistered if campaigns will display one |
| `website` | `website_or_social_url` | Normalized HTTPS URL with SSRF-safe validation. | Optional | Required for the current registered-company branch |
| `description` | `description` | Trimmed 30-240 character creator-facing description. | Optional | Required for the current registered-company branch |
| `team` | `team_size` | One versioned team-size option. | Not applicable | Required for the current registered-company branch |
| `fund` | `funded_content_categories` | 2-5 unique versioned category keys. | Required | Required |
| `workflow` | `production_workflow` | One versioned workflow key. | Not currently asked | Required for business accounts |
| `view` | `watched_content_categories` | 2-5 unique versioned category keys, separate from funded lanes. | Required | Required |
| `discovery` | `discovery_source` | One versioned option key plus optional bounded free text for `other`. | Required | Required |
| `campaignGoal` | `campaign_goal` | One versioned campaign-goal key. | Required | Required |
| `budget` | `budget_range` | One versioned budget-range key. This is preference data, not a funding commitment. | Required | Required |

Changing `funder_type` or `company_registered` must cause the server to recalculate required steps. The API must never silently keep contradictory business-only answers on an individual branch. Completion returns the normalized organisation/funder profile, verification requirement/status, completion timestamp, and `/brand` destination.

### Onboarding authorization and behavior

- Only the authenticated account may read or mutate its onboarding draft.
- Creator endpoints reject organisation accounts and organisation endpoints reject creator accounts with `403`.
- Email verification may be required for completion, but draft saving should work before verification so progress is not lost.
- Every PATCH is idempotent and guarded by a revision to prevent two tabs from overwriting newer answers.
- Completion is one database transaction. A half-completed profile must never be visible.
- Photo skipping is represented by `photo_upload_id: null`; it is the only optional frontend step. All other branch-relevant answers are compulsory.
- Uploaded images remain untrusted until ownership, MIME, scan, and processing state pass.
- Returning users with completed onboarding are routed to their workspace. They may edit supported fields through profile/settings endpoints, not by reopening onboarding.
- Admin user detail may display onboarding status and final answers, but admin staff must not edit customer preferences through the onboarding endpoints.
- Record schema version so future questions can be added without pretending old users answered them.

## D. Product configuration, handles, and public profiles

The campaign builder, onboarding choices, creator settings, public creator profile, and platform badges currently rely on hard-coded frontend data. Public profile responses must never expose connected-account tokens, private email, bank data, exact payout amounts, trust internals, or unpublished work.

| Priority | Method and path | Required contract |
|---|---|---|
| Missing P0 | `GET /product-config` | Return customer-safe runtime rules: supported country/currency, hold period, minimum withdrawal, funding fee, enabled platforms and connection state, campaign pot/rate/duration limits, upload limits, and current legal-document versions. Cacheable and versioned. |
| Missing P1 | `GET /handles/{handle}/availability` | Normalize a proposed public handle and return availability/reservation reason without leaking private accounts. Rate limited. |
| Missing P0 | `GET /profiles/creators/{handle}` | Public creator profile with handle, display name, photo, bio, location at the chosen privacy precision, availability, content lanes, verified aggregate stats, and a bounded list of approved public campaign work. |
| Missing P1 | `GET /profiles/creators/{handle}/clips` | Cursor-paginated approved public portfolio; never return rejected, processing, withdrawn, private, or disputed clips. |
| Missing P1 | `GET /profiles/organisations/{slug}` | Public brand/funder identity, verification badge, description, website, logo, and public live/completed campaign summary. |

No separate endpoint is required to edit handle, location, lane, public visibility, or availability if `PUT /creators/me/profile` is expanded to support them with uniqueness/privacy validation. The current profile schema does not support those fields and must be widened. Likewise `PUT /organisations/me/profile` must support a stable public slug if organisation profiles are exposed.

**2026-09-22 — Built**: all five rows. `creator_profiles.handle` and `organisation_profiles.slug` (both nullable — no public page exists before one is set) plus a `public_profile` toggle on each, edited through the existing `PUT` profile routes (as this section anticipated) with uniqueness checked across *both* tables — a creator's handle and a brand's slug share one namespace, so `GET /handles/{handle}/availability` checks both. Not modeled: `location` (no location field exists anywhere yet — see the still-open field-contract gap in §C) and a separate "availability for briefs" flag. Public creator stats are `approved_clips` and lifetime `verified_views` (summed from `EarningAccount.cumulative_views`, never a payout amount); `recent_work` is the 6 most recent approved, non-withdrawn submissions. `/handles/.../availability` isn't rate-limited yet (P1 in the row, not done).

## E. Creator identity verification/KYC

The payout-account UI says the bank name must match a verified identity, but the backend has no creator identity-verification record or workflow. The exact evidence and provider must be approved by payment/compliance counsel; Clippit should prefer a hosted verification session and avoid storing raw identity documents or numbers unless necessary.

| Priority | Method and path | Required contract |
|---|---|---|
| Missing P0 | `POST /creators/me/verification/session` | Create or resume an idempotent hosted identity-verification session and return provider URL/token, expiry, required checks, and application ID. |
| Missing P0 | `GET /creators/me/verification` | Return `not_started`, `pending`, `needs_action`, `verified`, `rejected`, or `expired`, with customer-safe reasons and retry/resubmission rules. |
| Missing P0 | `POST /webhooks/identity` | Verify the identity provider signature, store provider event ID, update the application idempotently, and notify the creator. |
| Missing P0 | `GET /admin/creators/verifications` | Paginated creator-verification queue with state, risk, age, provider, and assignee filters. |
| Missing P0 | `GET /admin/creators/verifications/{application_id}` | Secure operator detail with provider checks, minimally necessary identity data, bank-name comparison, prior decisions, and audit events. |
| Missing P0 | `POST /admin/creators/verifications/{application_id}/approve` | Audited manual approval available only under documented policy. |
| Missing P0 | `POST /admin/creators/verifications/{application_id}/reject` | Audited rejection/needs-action decision with structured customer-safe reasons. |

Bank verification and identity verification are separate: account resolution proves an account exists; it does not by itself prove the Clippit user owns the identity.

## F. Social-token lifecycle, provider compliance, and YouTube

| Priority | Method and path | Required contract |
|---|---|---|
| Missing P0 | `POST /social/{platform}/refresh` | Refresh an expiring provider token when supported; update encrypted credentials atomically and surface `reconnect_required` when refresh is impossible. This may normally be called by a worker rather than the browser. |
| Missing P1 | `POST /social/{platform}/sync-profile` | Re-read the connected handle/display name and connection health after permission changes. |
| Missing P0 | `POST /webhooks/social/{platform}/deauthorize` | Verify the provider request and disconnect/revoke the affected account when a user removes Clippit at the platform. |
| Missing P0 | `POST /webhooks/social/{platform}/data-deletion` | Satisfy Meta/platform data-deletion callbacks and return the required confirmation/status reference. |

No new public path is needed for YouTube because the generic login/callback and account-list paths already exist. The missing work is a YouTube OAuth provider, token refresh, channel identity, video lookup/metrics adapter, quota handling, ingestion tests, and enabling `connectable` only after those pass.

## G. Creator participation in campaigns

The PRD explicitly says a creator joins a campaign. The current API infers participation only after submission, which cannot correctly power Joined filters, capacity rules, or pre-submission campaign updates.

| Priority | Method and path | Required contract |
|---|---|---|
| Missing P0 | `POST /campaigns/{campaign_ref}/join` | Join an open campaign after checking role, required connected account, capacity/caps, campaign state, and duplicate membership. Idempotent. |
| Missing P0 | `DELETE /campaigns/{campaign_ref}/join` | Leave before an accepted submission exists; preserve historical membership and refuse invalid withdrawal after earning begins. |
| Missing P0 | `GET /creators/me/campaigns` | List joined, submitted, active, completed, and left campaigns with cursor pagination. |
| Missing P1 | `DELETE /campaigns/{campaign_ref}` | Permanently delete an unfunded draft owned by the organisation. Refuse once funding or submissions exist. |
| Missing P1 | `POST /campaigns/{campaign_ref}/duplicate` | Copy an owned campaign into a new unfunded draft without copying transactions, submissions, dates, or provider references. |

**2026-09-22 — Built**: a new `campaign_memberships` table backs `POST`/`DELETE /campaigns/{campaign_ref}/join` (idempotent join, requires a connected account for one of the campaign's platforms, refuses leaving after an approved submission) and `GET /creators/me/campaigns` (joined/submitted/active/completed/left, filterable by `membership_status`). `joined`/`open` feed filters and the `joined`/`feed_status` card fields now read membership as well as submissions, so a creator who joined without submitting still shows as Joined. Pagination is `limit`/`offset`, matching every other list route today, not the cursor pagination this section calls for — that's a cross-cutting change (see "Existing contract corrections" below), not specific to this endpoint. Headcount capacity/caps aren't modeled (there's no max-creators field on a campaign yet) so that check is a no-op. `DELETE /campaigns/{campaign_ref}` and `POST .../duplicate` are still missing.

Campaign editing does not need a new endpoint: `PATCH /campaigns/{campaign_ref}`, `PUT .../rules`, and `PUT .../payout-rule` already cover it.

## H. Campaign-studio drafts, source assets, analytics, and closeout

The six-screen campaign studio currently persists only to browser `localStorage`. `POST /campaigns` cannot autosave the early screens because its schema requires title, description, platform, budget, and payout rule together. Production needs a resumable server draft before a fully valid Campaign can be created.

### Campaign studio drafts

| Priority | Method and path | Required contract |
|---|---|---|
| Missing P0 | `POST /campaign-drafts` | Create an empty owned studio draft with schema version, revision, current step, and expiry policy. Return a stable draft ID. |
| Missing P0 | `GET /campaign-drafts` | List the organisation's in-progress studio drafts so work can resume across devices. |
| Missing P0 | `GET /campaign-drafts/{draft_id}` | Return the owned canonical draft, completed/required steps, validation blockers, revision, and updated time. |
| Missing P0 | `PATCH /campaign-drafts/{draft_id}` | Autosave any subset of details, cover, source material, rules, platforms, earning rules, end condition, pot, and rate with optimistic revision control. |
| Missing P0 | `DELETE /campaign-drafts/{draft_id}` | Delete an incomplete owned studio draft and detach unreferenced assets. Refuse if it was finalized. |
| Missing P0 | `POST /campaign-drafts/{draft_id}/finalize` | Validate all campaign invariants, atomically create the canonical unfunded Campaign and checklist, consume the draft, and return the campaign ID/slug and funding next route. Idempotent. |

The existing `POST /campaigns` remains useful for API clients that already have a complete campaign payload. The frontend campaign studio should use the draft lifecycle.

### Campaign source materials

| Priority | Method and path | Required contract |
|---|---|---|
| Missing P0 | `POST /uploads/campaign-assets` | Upload owned audio, image, video, PDF, or approved document source material with scan/processing state and short-lived signed access. |
| Missing P0 | `GET /campaigns/{campaign_ref}/assets` | Return creator-visible ordered source assets with type, title, duration/size, processing state, and signed download/stream URL. Hide unsafe/unready assets. |
| Missing P0 | `POST /campaigns/{campaign_ref}/assets` | Attach an owned completed upload or validated external HTTPS link to an unfunded draft campaign. |
| Missing P1 | `PATCH /campaigns/{campaign_ref}/assets/{asset_id}` | Rename, replace link metadata, change visibility, or update creator-facing description while terms remain editable. |
| Missing P1 | `DELETE /campaigns/{campaign_ref}/assets/{asset_id}` | Detach an asset from an editable campaign and schedule unreferenced private media for deletion. |
| Missing P1 | `PUT /campaigns/{campaign_ref}/assets/order` | Replace the complete ordered asset-ID list with ownership and membership validation. |

For campaign-studio drafts, equivalent asset attachment may be accepted directly by `PATCH /campaign-drafts/{draft_id}` until finalization.

### Live analytics and completed closeout

| Priority | Method and path | Required contract |
|---|---|---|
| Missing P0 | `GET /campaigns/{campaign_ref}/analytics` | Authorised time series for verified views, spend, pot remaining, submissions, approvals, platforms, and reading freshness with bounded date range/granularity. Powers real sparklines instead of static bars. |
| Missing P0 | `GET /campaigns/{campaign_ref}/closeout` | Immutable final campaign summary: close reason/time, pot, creator earnings, refundable/returned funds, verified views, approved creators/clips, platform delivery, top clips, review outcomes, and reconciliation state. |
| Missing P0 | `GET /campaigns/{campaign_ref}/closeout.pdf` | Server-generated official one-page or paginated closeout document from immutable data with verification reference/digest. |
| Missing P1 | `GET /campaigns/{campaign_ref}/activity` | Cursor-paginated customer-safe campaign lifecycle events: created, terms changed, funding, opened, paused/resumed, reviews, low pot, closed, settlement, refund. |

The existing CSV `GET /campaigns/{campaign_ref}/report` remains the machine-readable export. It does not replace analytics or the closeout record.

## I. Submission corrections and earnings provenance

| Priority | Method and path | Required contract |
|---|---|---|
| Missing P0 | `POST /submissions/{submission_id}/resubmit` | Create a corrected submission linked to the rejected/correction-requested predecessor after validating campaign state, platform ownership, URL/file, and retry policy. Preserve the original verdict and appeal history. |
| Missing P0 | `GET /earnings/entries/{entry_id}` | Return one owned earning entry with campaign, clip, whole-thousand calculation, rate, cap effects, hold/payable state, and immutable platform snapshot provenance. This is how every naira can be traced to a platform reading. |
| Missing P1 | `GET /earnings/export` | Date/campaign-filtered creator earnings CSV with safe cells and ledger references. |
| Missing P1 | `GET /earnings/statement.pdf` | Server-generated creator earnings statement for a bounded period, distinct from an individual payout receipt. |

Processing progress, approved/rejected verdicts, appeals, clip detail, performance, and clip earnings already resolve through the existing submission endpoints; they need dynamic IDs in the frontend, not duplicate APIs.

## J. Brand ledger, refunds, statements, official receipts, and public verification

The frontend currently fabricates brand transactions and prints client-rendered receipts. Official financial records must come from the server-side ledger.

| Priority | Method and path | Required contract |
|---|---|---|
| Missing P0 | `GET /organisations/me/transactions` | Cursor-paginated ledger of funding, fees, creator allocations, refunds, and adjustments with filters for campaign, type, status, and date. |
| Missing P0 | `GET /organisations/me/transactions/{transaction_id}` | Return one authorised immutable ledger item with sender, recipient, provider references, amount, currency, campaign, and audit-safe provenance. |
| Missing P1 | `GET /organisations/me/transactions/export` | Export a date-filtered CSV statement using formula-injection-safe cells. |
| Missing P0 | `POST /campaigns/{campaign_ref}/funding/quote` | Return server-calculated pot, fee/tax components, total, currency, supported methods, expiry, and terms version before creating/locking a funding order. |
| Missing P0 | `POST /campaigns/{campaign_ref}/refunds` | Create an idempotent refund of the legally refundable unused balance after close/cancellation and provider reconciliation. |
| Missing P0 | `GET /campaigns/{campaign_ref}/refunds` | Return refund amount, status, destination, provider reference, timestamps, and failure reason. |
| Missing P1 | `POST /payouts/quote` | Validate amount and destination and return fee, net amount, currency, and quote expiry without reserving money. |
| Missing P1 | `DELETE /creators/me/bank-details` | Remove the saved payout destination after step-up authentication when no payout is pending; preserve masked historical destination snapshots on existing receipts. |
| Missing P0 | `GET /payouts/{payout_id}/receipt.pdf` | Generate the creator's official one-page PDF from immutable server data, with a page-level watermark and verification code. |
| Missing P0 | `GET /organisations/me/transactions/{transaction_id}/receipt.pdf` | Generate the brand's official one-page transaction PDF from the ledger. |
| Missing P0 | `GET /campaigns/{campaign_ref}/funding/receipt.pdf` | Generate the official funding order/certificate PDF from provider-confirmed data. |
| Missing P0 | `GET /receipts/{reference}/verify` | Public, rate-limited verification response containing safe amount/status/date/type/issuer facts and a signed-document digest; never expose private bank or account data. |
| Missing P1 | `GET /organisations/me/invoices` | List fee/tax invoices or credit notes issued to the organisation, subject to the chosen provider and tax/accounting structure. |
| Missing P1 | `GET /organisations/me/invoices/{invoice_id}` | Return one authorised invoice/credit-note record with line items and linked funding/fee transaction. |
| Missing P1 | `GET /organisations/me/invoices/{invoice_id}.pdf` | Server-generated immutable invoice/credit-note PDF using the organisation's verified billing identity at issue time. |
| Missing P1 | `POST /admin/refunds/{refund_id}/retry` | Re-drive a retryable provider refund idempotently and audit the operator. |
| Missing P1 | `POST /admin/refunds/{refund_id}/fail` | Finalise an unrecoverable refund failure with an operator reason and escalation state. |

## K. Support centre and customer tickets

Support must serve both creator and brand accounts. A ticket belongs to the caller and may reference a campaign, submission, payout, funding order, or transaction.

| Priority | Method and path | Required contract |
|---|---|---|
| Missing P1 | `GET /support/categories` | Return help-centre categories and article counts. This can be backed by a CMS but must have a stable app contract. |
| Missing P1 | `GET /support/articles` | Search/list published support articles by category and query. |
| Missing P1 | `GET /support/articles/{slug}` | Return one published support article, revision, and updated time. |
| Missing P0 | `POST /support/tickets` | Create a ticket with category, subject, first message, optional resource reference, and owned attachment IDs. |
| Missing P0 | `GET /support/tickets` | List the caller's open and closed tickets with unread-reply counts. |
| Missing P0 | `GET /support/tickets/{ticket_id}` | Return an owned ticket and ordered message thread. |
| Missing P0 | `POST /support/tickets/{ticket_id}/messages` | Add a customer reply with optional owned attachments and reopen according to policy. |
| Missing P1 | `POST /support/tickets/{ticket_id}/close` | Allow the customer to close a resolved ticket. |
| Missing P1 | `POST /support/tickets/{ticket_id}/reopen` | Reopen within the allowed window or create a linked follow-up. |
| Missing P0 | `GET /admin/support/tickets` | Admin/support queue with status, category, role, assignee, priority, age, and resource filters. |
| Missing P0 | `GET /admin/support/tickets/{ticket_id}` | Operator view including thread, safe customer context, related resources, and audit history. |
| Missing P0 | `POST /admin/support/tickets/{ticket_id}/messages` | Add an operator reply and notify the customer. |
| Missing P0 | `PATCH /admin/support/tickets/{ticket_id}` | Assign, change priority/status/category, and record internal disposition. |
| Missing P1 | `POST /admin/support/tickets/{ticket_id}/notes` | Add an internal-only note that is never returned to the customer endpoint. |

If Clippit owns help content instead of using an external CMS, the following content-management routes are also required:

| Priority | Method and path | Required contract |
|---|---|---|
| Conditional P1 | `GET /admin/support/categories` | List draft/published categories and ordering. |
| Conditional P1 | `POST /admin/support/categories` | Create a category with unique slug and audit author. |
| Conditional P1 | `PATCH /admin/support/categories/{category_id}` | Rename/reorder/archive a category without breaking article URLs. |
| Conditional P1 | `GET /admin/support/articles` | Search all draft/published articles and revisions. |
| Conditional P1 | `POST /admin/support/articles` | Create a draft article with category, slug, body, locale, and author. |
| Conditional P1 | `PATCH /admin/support/articles/{article_id}` | Create a new editable revision rather than silently replacing published content. |
| Conditional P1 | `POST /admin/support/articles/{article_id}/publish` | Publish one reviewed revision and update cache/version. |
| Conditional P1 | `POST /admin/support/articles/{article_id}/unpublish` | Remove from public discovery while preserving revisions and existing ticket references. |

## L. Financial disputes and safety reports

Support tickets answer questions. Disputes and safety reports change risk, money, or moderation state and therefore require structured reasons, evidence, deadlines, assignment, decisions, and immutable audit history.

### Customer disputes

| Priority | Method and path | Required contract |
|---|---|---|
| Missing P0 | `POST /disputes` | Open one structured dispute against an authorised submission verdict, earning entry, payout, funding order, refund, or transaction. Enforce type-specific time windows and prevent duplicate open cases. |
| Missing P0 | `GET /disputes` | List the caller's disputes with type, resource reference, status, deadline, last update, and unread reply count. |
| Missing P0 | `GET /disputes/{dispute_id}` | Return an owned case, customer-visible evidence, decision history, deadlines, and messages. |
| Missing P0 | `POST /disputes/{dispute_id}/messages` | Add a customer response and owned evidence upload IDs without altering the original claim. |
| Missing P1 | `POST /disputes/{dispute_id}/withdraw` | Let the opener withdraw an unresolved dispute while preserving its audit record. |
| Missing P0 | `GET /admin/disputes` | Paginated operator queue filtered by type, money at risk, deadline, state, customer role, assignee, and age. |
| Missing P0 | `GET /admin/disputes/{dispute_id}` | Operator view containing the case, related immutable ledger/trust records, customer messages, evidence, and audit timeline. |
| Missing P0 | `PATCH /admin/disputes/{dispute_id}` | Assign, prioritize, request information, or change workflow state with optimistic concurrency. |
| Missing P0 | `POST /admin/disputes/{dispute_id}/resolve` | Apply a structured upheld/denied/partial resolution and invoke only approved domain actions such as verdict override, payout retry, or refund. Never edit history directly. |
| Missing P1 | `POST /admin/disputes/{dispute_id}/reopen` | Reopen under policy with an operator reason and a new resolution deadline. |

The existing creator appeal endpoint remains the fast, submission-specific first review. A dispute is the escalated case after ordinary appeal/review or for money operations.

### Customer safety and abuse reports

| Priority | Method and path | Required contract |
|---|---|---|
| Missing P0 | `POST /reports` | Report an accessible campaign, public profile, source asset, or public clip using a structured reason, optional text, and evidence. Rate limit and protect the reporter's identity. |
| Missing P1 | `GET /reports/me` | Return the reporter's own cases and customer-safe statuses without exposing moderation notes. |
| Missing P0 | `GET /admin/reports` | Moderation queue filtered by target type, severity, reason, status, age, and assignee. |
| Missing P0 | `GET /admin/reports/{report_id}` | Return report evidence, target snapshot, related reports, account/campaign context, and audit data. |
| Missing P0 | `POST /admin/reports/{report_id}/resolve` | Record no-action, content restriction, campaign pause, account sanction, or escalation through audited domain services. |

## M. Business verification/KYB

The current admin API can flip a boolean, but there is no application, evidence, review queue, rejection reason, or resubmission trail.

| Priority | Method and path | Required contract |
|---|---|---|
| Missing P0 | `POST /uploads/documents` | Upload an owned KYB/support document using stricter types, scanning, encryption, retention, and access controls than public media. |
| Missing P0 | `POST /organisations/me/verification` | Submit legal name, registration number, address, representatives, document IDs, and attestations. Version every application. |
| Missing P0 | `GET /organisations/me/verification` | Return status, submitted time, safe checks, required corrections, decision reason, and resubmission eligibility. |
| Missing P0 | `GET /admin/organisations/verifications` | Paginated KYB queue with status, risk, age, and assignee filters. |
| Missing P0 | `GET /admin/organisations/verifications/{application_id}` | Return the application, secure document links, previous decisions, and related account risk/audit data. |
| Missing P0 | `POST /admin/organisations/verifications/{application_id}/approve` | Approve with legal identity fields and an auditable decision. |
| Missing P0 | `POST /admin/organisations/verifications/{application_id}/reject` | Reject/request corrections with structured reasons and customer-safe copy. |
| Missing P1 | `POST /organisations/me/finance-email/change/request` | Send verification to a new finance email after step-up authentication; do not change receipt/closeout delivery yet. |
| Missing P1 | `POST /organisations/me/finance-email/change/confirm` | Consume the code, switch the finance contact, notify the previous address, and audit the change. |

The existing `POST /admin/organisations/{user_id}/verify-business` should become an audited emergency override, not the normal verification workflow.

## N. Admin users, campaigns, moderation, trust, and fraud

The PRD explicitly requires a flagged-submissions queue. Current admin endpoints expose counts and blocked earnings but not an operable investigation queue.

| Priority | Method and path | Required contract |
|---|---|---|
| Missing P0 | `GET /admin/users` | Search/filter creators, organisations, and admins by state, verification, risk, creation date, and recent activity. |
| Missing P0 | `GET /admin/users/{user_id}` | Return safe identity/profile, verification, sessions summary, connected-platform health, money summary, sanctions, and audit timeline. |
| Missing P0 | `POST /admin/users/{user_id}/suspend` | Suspend access/earning/funding with scope, reason, duration, and customer notification. Never delete ledger history. |
| Missing P0 | `POST /admin/users/{user_id}/restore` | Restore a suspended account after recording reason and operator. |
| Missing P1 | `POST /admin/users/{user_id}/force-logout` | Revoke all sessions for a compromised account and notify the customer. |
| Missing P1 | `POST /admin/users/{user_id}/reset-2fa` | High-risk, separately permissioned recovery action that invalidates 2FA/recovery codes after documented identity checks and notifies the user. Require reason and, if policy demands, second approval. |
| Missing P0 | `GET /admin/submissions/flagged` | Paginated flagged-submission queue with platform, campaign, creator, risk rule, severity, amount at risk, age, and assignment. |
| Missing P0 | `GET /admin/submissions` | Global submission search/filter across lifecycle, verification, appeal, platform, campaign, creator, trust, tracking, and date; flagged is also available as a filter. |
| Missing P0 | `GET /admin/submissions/{submission_id}` | Investigation view with public post, stored snapshots, trust features, requirements, earnings exposure, related accounts, comments, and audit trail. |
| Missing P0 | `POST /admin/submissions/{submission_id}/trust/clear` | Clear the flag, record reason/evidence, resume eligible settlement/tracking, and notify affected parties. |
| Missing P0 | `POST /admin/submissions/{submission_id}/trust/confirm` | Confirm fraud, block affected earnings, stop tracking, record sanction/recovery actions, and notify under policy. |
| Missing P1 | `POST /admin/submissions/{submission_id}/assign` | Assign/unassign an investigator and enforce optimistic concurrency on decisions. |
| Missing P0 | `GET /admin/campaigns` | Search/filter all campaigns by owner, state, funding, risk, review backlog, pot, and dates. |
| Missing P0 | `GET /admin/campaigns/{campaign_ref}` | Full operator view of terms, owner, funding, submissions, pot ledger, flags, and audit trail. |
| Missing P0 | `POST /admin/campaigns/{campaign_ref}/pause` | Emergency pause with reason and notification, distinct from the brand's normal pause action. |
| Missing P0 | `POST /admin/campaigns/{campaign_ref}/close` | Emergency close with reason, final settlement/refund plan, and audit record. |
| Missing P1 | `GET /admin/refunds` | List/filter refund operations and failures. |
| Missing P1 | `POST /admin/payouts/{payout_id}/reconcile` | Ask the provider for authoritative state and apply an idempotent reconciliation result. |
| Missing P0 | `GET /admin/earnings` | Search/filter all immutable earning entries by creator, campaign, submission, hold/payable/allocated state, trust block, and snapshot reference. |
| Missing P0 | `GET /admin/earnings/{entry_id}` | Full provenance view for one earning entry, including calculation, caps, snapshot, allocations, payout, and audit events. |
| Missing P0 | `POST /admin/earnings/{submission_id}/hold` | Place a scoped, reasoned investigation/compliance hold on future release without deleting accruals or snapshots; notify under policy. |
| Missing P0 | `POST /admin/earnings/{submission_id}/release` | Release an operator hold after documented resolution; do not bypass campaign pot, cap, trust, or statutory constraints. |
| Missing P0 | `GET /admin/ledger` | Unified immutable finance ledger across collections, campaign funds, fees, creator accruals, payout allocations, transfers, refunds, reversals, and adjustments. |
| Missing P0 | `GET /admin/ledger/{entry_id}` | One ledger event with debit/credit accounts, references, provider correlation, provenance, and linked audit events. |
| Missing P1 | `GET /admin/ledger/export` | Strictly permissioned, date/type/account-filtered finance export with request audit and safe cells. |
| Missing P1 | `GET /admin/reconciliation` | Provider-versus-Clippit reconciliation runs, unmatched items, age, amount, and resolution state. |
| Missing P1 | `POST /admin/reconciliation/run` | Start an idempotent bounded reconciliation job for a provider/date range and return job ID. |
| Missing P1 | `GET /admin/audit/{event_id}` | Return one full audit event with request/provider correlation fields. |
| Missing P1 | `GET /admin/audit/export` | Export filtered audit data for an incident or finance review with strict permissions. |
| Missing P1 | `GET /admin/jobs` | Return scheduled-job last run, next run, lease owner, duration, processed count, and last error. |
| Missing P1 | `POST /admin/jobs/{job_name}/run` | Run one allowlisted job with an idempotency key and audit record. This supersedes one-off settle/sweep buttons over time. |

## O. Admin operator access, trust configuration, and provider operations

Admin accounts cannot be self-created, which is correct, but there is currently no controlled provisioning, permission, deprovisioning, or operator-session surface. Production administration must use named people, MFA, least privilege, short sessions, and complete audit records.

### Operator lifecycle and permissions

| Priority | Method and path | Required contract |
|---|---|---|
| Missing P0 | `GET /admin/operators` | List named operators, roles/permissions, MFA state, status, last activity, and inviter. Restricted to owner/security-admin permission. |
| Missing P0 | `POST /admin/operators/invitations` | Invite an email to an allowlisted operator role with short expiry, one-time token, mandatory MFA setup, and audited inviter. |
| Missing P0 | `GET /auth/admin-invitations/{token}` | Return a minimal valid/expired/already-used invitation description without exposing other operators. |
| Missing P0 | `POST /auth/admin-invitations/{token}/accept` | Verify email, establish credentials, require MFA enrollment, consume the invitation once, and create the operator. |
| Missing P0 | `PATCH /admin/operators/{operator_id}` | Change allowlisted role/permissions or profile under separation-of-duties rules; prevent self-escalation. |
| Missing P0 | `POST /admin/operators/{operator_id}/suspend` | Revoke all operator sessions immediately and disable access while preserving audit history. |
| Missing P1 | `POST /admin/operators/{operator_id}/restore` | Restore access without bypassing MFA or invitation policy. |
| Missing P0 | `GET /auth/permissions` | Return the current user's effective permissions so admin UI and API enforcement share one truth. |

### Trust rules and random audits

| Priority | Method and path | Required contract |
|---|---|---|
| Missing P0 | `GET /admin/trust/rules` | Return versioned active and draft fraud/trust thresholds, applicability, author, validation state, and activation time. |
| Missing P0 | `POST /admin/trust/rules` | Create a new immutable draft rule version after schema validation; never edit the active version in place. |
| Missing P0 | `POST /admin/trust/rules/{version_id}/activate` | Activate a tested version with approver, reason, effective time, and rollback reference. |
| Missing P0 | `GET /admin/submissions/random-audits` | Queue statistically sampled unflagged submissions so precision and recall can both be measured. |
| Missing P0 | `POST /admin/submissions/{submission_id}/trust/review` | Record a labelled random-audit or investigation outcome using the internal trust review service, with required source and evidence. |

### Provider/webhook operations

| Priority | Method and path | Required contract |
|---|---|---|
| Missing P1 | `GET /admin/providers` | Operational health for payment, email, storage, identity, transcription, AI, and each social adapter: configured state, last success/failure, latency, quota, and circuit state. Never expose secrets. |
| Missing P1 | `GET /admin/webhooks` | Filter stored webhook envelopes by provider, event kind, handled state, reference, date, and retry state. |
| Missing P1 | `GET /admin/webhooks/{event_id}` | Return one redacted verified event, signature result, handler attempts, linked resource, and outcome. |
| Missing P1 | `POST /admin/webhooks/{event_id}/replay` | Replay one allowlisted failed handler idempotently without re-verifying a modified payload; audit the operator. |
| Missing P1 | `POST /webhooks/email` | Verify email-provider events and record delivered, bounced, deferred, complained, or unsubscribed state for transactional/optional mail policy. |

## P. Production media lifecycle

The existing streaming upload routes are acceptable for development and small pilots. Large creator videos should not pass through a single web worker in production.

| Priority | Method and path | Required contract |
|---|---|---|
| Missing P0 | `POST /uploads/multipart` | Create an owned R2 multipart upload after validating intended kind, filename, declared size, and content type; return short-lived signed part URLs. |
| Missing P0 | `POST /uploads/multipart/{upload_id}/complete` | Verify uploaded parts, size, byte signature, checksum, and ownership; queue scan/transcode/thumbnail work. |
| Missing P1 | `GET /uploads/{upload_id}` | Return owner-safe metadata and processing/scan state, plus a short-lived signed read URL when allowed. |
| Missing P1 | `DELETE /uploads/{upload_id}` | Delete an unattached owned upload or schedule deletion under retention rules. Refuse deletion when referenced by immutable evidence/finance records. |
| Missing P1 | `POST /uploads/support-attachments` | Upload ticket attachments under support-specific type, size, scanning, and access rules. This may reuse the multipart implementation. |

`GET /media/{key:path}` must be disabled in production once signed R2 delivery is active.

## Q. Notification delivery beyond the inbox

| Priority | Method and path | Required contract |
|---|---|---|
| Missing P1 | `GET /notifications/unread-count` | Cheap shell badge count without downloading the full inbox. |
| Missing P1 | `POST /notifications/{notification_id}/archive` | Hide one owned notification while preserving the audit/event record. |
| Missing P1 | `POST /push-subscriptions` | Register/update a browser push subscription for the current session and preference state. |
| Missing P1 | `DELETE /push-subscriptions/{subscription_id}` | Remove one owned push subscription on logout, revocation, or browser unsubscribe. |

Push can be deferred during a controlled pilot if in-app and transactional email delivery are operational.

## R. Legal documents and consent records

The frontend currently links to `/terms` and `/privacy`, but those pages do not exist. The pages may be statically rendered; the acceptance record still belongs in the backend.

| Priority | Method and path | Required contract |
|---|---|---|
| Missing P0 | `GET /legal/documents/{slug}` | Return the currently published Terms, Privacy Policy, Community Rules, or campaign-funding terms with immutable version and effective date. A static frontend can consume this at build time. |
| Missing P0 | `POST /legal/acceptances` | Record user, document/version, accepted time, IP/user-agent hash, and the action that required consent. Idempotent per version. |
| Missing P1 | `GET /legal/acceptances/me` | Return the caller's accepted versions and any newly required consent. |

**2026-09-22 — Built**: content lives in a small static, versioned registry (`modules/legal/documents.py` — deployed with the app, per the "may be statically rendered" note), so the conditional `/admin/legal/*` CRUD rows below weren't built. `POST /legal/acceptances` is idempotent per `(user, slug, version)` and 409s on a stale version. **The four documents' bodies are placeholder text, not real legal copy** — this needs counsel review before launch. `product-config`'s `legal` array exposes the current versions.

If legal documents are managed in Clippit rather than versioned files deployed with the application:

| Priority | Method and path | Required contract |
|---|---|---|
| Conditional P1 | `GET /admin/legal/documents` | List slugs, versions, effective dates, publication state, and acceptance counts. |
| Conditional P1 | `POST /admin/legal/documents/{slug}/versions` | Create an immutable draft version with checksum and counsel/author metadata. |
| Conditional P1 | `POST /admin/legal/documents/{slug}/versions/{version}/publish` | Publish with effective date and whether re-acceptance is mandatory; never rewrite an accepted version. |

## S. Automated brief verification and media processing

These are internal contracts. They are needed only if verification/transcoding run outside the FastAPI process, which is the recommended production topology.

| Priority | Method and path | Required contract |
|---|---|---|
| Conditional P0 | `POST /internal/submissions/{submission_id}/verification/start` | Idempotently enqueue transcription, frame sampling, brief checks, and decision aggregation. |
| Conditional P0 | `GET /internal/submissions/{submission_id}/verification` | Return internal stage state, attempts, model/provider versions, safe failure codes, and resulting requirement checks. |
| Conditional P0 | `POST /internal/submissions/{submission_id}/verification/callback` | Signed worker callback that stores requirement-level evidence and the final verifier decision exactly once. |
| Conditional P1 | `POST /internal/uploads/{upload_id}/processed` | Signed media-worker callback for scan, duration, dimensions, normalized video, waveform, and thumbnail assets. |

If these jobs remain in-process, expose no extra HTTP routes; call the same service functions directly. The product still needs the worker behavior, retries, dead-letter queue, and audit data.

## T. Internal performance aggregates and optional service-split contracts

The intelligence contract names two aggregate reads that are not implemented. They are useful to campaign analytics, creator profile aggregates, trust investigations, and support without forcing each consumer to rebuild snapshot logic.

| Priority | Method and path | Required contract |
|---|---|---|
| Missing P1 | `GET /internal/campaigns/{campaign_id}/performance` | Stored campaign-level platform totals/time series, freshness, coverage, and trust distribution derived from snapshots; never call platforms during the read. |
| Missing P1 | `GET /internal/creators/{creator_id}/performance` | Stored creator-level approved public performance aggregates with campaign/platform breakdown and trust-safe visibility. |

The following endpoints are **conditional**, not required inside the current monolith. Implement them only if core domains are deployed as separate services; otherwise keep direct service calls so there is not a fake network boundary inside one process.

| Priority | Method and path | Required contract |
|---|---|---|
| Conditional P1 | `GET /internal/campaigns/{campaign_id}` | Canonical campaign state, platforms, owner, terms, and payout rules for another trusted service. |
| Conditional P1 | `GET /internal/submissions/{submission_id}` | Canonical submission identity, URL, creator, campaign, platform, and lifecycle state. |
| Conditional P0 | `GET /internal/campaigns/{campaign_id}/balance` | Authoritative available/committed/refundable campaign ledger balance. |
| Conditional P0 | `POST /internal/campaigns/{campaign_id}/debit` | Idempotently reserve/debit a campaign using a payout/earning reference; hard-refuse overspend. |
| Conditional P1 | `GET /internal/payouts` | Restricted payout query for a separate admin/finance service. |
| Conditional P0 | `POST /internal/payouts/{payout_id}/override` | Audited retry/fail/reconcile command executed by the money-owning service, never by an admin service directly. |

---

# Part III: existing routes that need production changes, not replacements

## Frontend integration

The largest current product gap is not an endpoint count: the Next.js frontend still reads fixtures and `localStorage`. Every relevant form, list, badge, dashboard, receipt, and state transition must be moved to the API inventory above with:

- one typed API client;
- authenticated server/client request handling;
- refresh/retry behavior that never repeats non-idempotent money actions unsafely;
- route guards by role, verification, and onboarding state;
- real loading, empty, partial, provider-outage, validation, forbidden, conflict, rate-limit, and retry states;
- cache invalidation after mutations;
- no customer financial or identity truth stored only in browser storage.

The current onboarding components are a concrete example of this gap: they write all answers to `localStorage`, while the two backend completion schemas omit several questions. The production integration must use the onboarding GET/PATCH/complete lifecycle above and remove browser storage as the source of truth.

## Onboarding persistence and migration

- Add durable creator and organisation onboarding-draft storage with revision, schema version, current step, answer timestamps, status, and completion time.
- Add structured location fields or a normalized location object.
- Split creator `interests` into content made and content watched; do not collapse them back into one list.
- Add organisation preferred user name, funder type, registration state, content-to-fund lanes, content-to-view lanes, and discovery source.
- Preserve profile fields used after onboarding in the normal profile tables; preserve research/personalization answers in dedicated typed columns or versioned answer records.
- Backfill existing completed profiles into a legacy onboarding version without inventing answers for questions they were never asked.
- Never treat a missing legacy answer as customer consent or as an explicit preference.

## Existing contract corrections found by the screen audit

- `PUT /creators/me/profile` must add handle, structured location, primary/content lanes, public visibility, and available-for-briefs fields. The current settings screen edits these values but the schema cannot store them.
- `GET /creators/me/profile` must return the same fields plus handle-change limits and safe public-profile URL.
- `PUT /organisations/me/profile` must distinguish the workspace user's preferred name from the public organisation/funder name and support a stable public slug if brand profiles are enabled.
- ~~`POST /campaigns` and `PATCH /campaigns/{campaign_ref}` must model the end condition explicitly. `duration_days = null` means **no calendar deadline; close only when the pot is exhausted or an authorised actor closes it**. The current funding service incorrectly converts null to a default 14-day deadline.~~ **Fixed 2026-09-22**: `funding.service.open_campaign` no longer defaults a null `duration_days` to 14; `ends_at` stays null and the rest of the codebase already treated `ends_at is None` as no-deadline correctly (list filters, `time_left`, `is_open_for_entries`, the sweep job). The explicit end-condition field on create/update responses (separate from just `duration_days`/`ends_at`) is still not modeled.
- Campaign create/update responses must expose source assets, end condition, close policy, funding lock state, and revision. A single `source_link` cannot power the sound plus visual-reference UI.
- Campaign money schema fields currently use Python `float` in several Pydantic models. They must accept/return decimal money values consistently with the NUMERIC ledger.
- `GET /campaigns`, `/submissions`, `/campaigns/{ref}/submissions`, `/earnings/history`, `/leaderboard`, `/notifications`, review queues, and every admin list need consistent cursor pagination and total/next-cursor metadata. Offset may remain for exports but is not the primary customer pagination contract.
- `GET /campaigns/{ref}/stats` must not fabricate a countdown for budget-only campaigns and must report why/when a campaign can close.
- `GET /campaigns/{ref}/report` must record the export request and derive every money/view field from immutable ledger and snapshot provenance.
- `POST /webhooks/payments` currently verifies and handles events but does not persist a provider-event envelope before dispatch. Store event ID/digest, signature result, redacted body, attempts, handler result, and linked resource for deduplication and operations.
- `POST /payouts` already carries an idempotency key in the body; standardize on an `Idempotency-Key` header or document the body field consistently across all money mutations.
- `POST /creators/me/bank-details/verify` must compare resolved name against the verified identity under a documented fuzzy/exact-match policy. Account resolution alone must not set identity verification.
- `GET /leaderboard` needs a privacy rule for displaying another creator's earnings. Prefer verified views/rank publicly unless the creator explicitly opts in to showing money.
- `GET /media/{key:path}` must not remain possession-only file access in production. Replace it with authorised short-lived signed URLs and disable the local route.
- `GET /openapi.json`, `/docs`, `/docs/oauth2-redirect`, and `/redoc` must be disabled or protected outside approved development/staging/operator access.
- The frontend must stop collecting raw card number, expiry, and CVV. `POST /campaigns/{ref}/funding` returns a provider-hosted checkout URL; card data must never touch Clippit's frontend or backend.
- Provider naming must be consistent in API responses, receipts, and UI. The PRD/frontend say Payaza while the implemented provider adapter is Paystack.

## Payment and money movement

- Select one provider name everywhere. The backend implements Paystack while parts of the frontend still say Payaza.
- Run live-shaped test-mode funding, webhook, refund, transfer, timeout, duplicate-event, reversal, and reconciliation rehearsals.
- Store provider event IDs and raw-event digests; never log card/bank secrets.
- Reconcile the Clippit ledger against provider statements, not only webhook state.
- Decide the legal escrow/collection structure and confirm that the provider account supports the campaign-to-many-creators flow.

## Social platforms and metrics

- Complete provider review/production access, especially TikTok and Meta.
- Encrypt social tokens at rest and rotate the encryption key safely.
- Implement Meta refresh and reconnect behavior.
- Build and verify the YouTube adapter.
- Add quota budgets, provider circuit breakers, exponential backoff, and customer-visible degraded states.
- Retain every view snapshot used for billing and make its provenance immutable.

## Automated content checking

- Implement R2 ingestion, safe FFmpeg processing, Deepgram transcription, frame sampling, and the verifier behind the existing `Verifier` interface.
- Store model/provider version, prompt/rule version, evidence timestamps, confidence, and human overrides.
- Do not auto-approve ambiguous or failed processing; route it to human review.
- Measure appeal overturn rate and freeze automatic decisions if quality thresholds fail.

## Email, jobs, storage, and observability

- Replace console email with a production sender, domain authentication, templates, bounce/complaint handling, and delivery monitoring.
- Move local uploads to R2 with signed URLs, scanning, lifecycle rules, and backups.
- Move periodic jobs out of the API process into one durable scheduler/queue with leases, retries, alerts, and dead-letter handling.
- Move rate limiting and shared cache state to Redis before running multiple application instances.
- Add Sentry/error monitoring, structured logs, request IDs, redaction, dashboards, and money-path alerts.
- Back up Postgres, test point-in-time recovery, and document restore/runbook procedures.

## Security and privacy

- Store refresh tokens and provider tokens hashed/encrypted as appropriate.
- Add CSRF protection to cookie-authenticated mutations.
- Add per-account and per-resource authorization tests for every object endpoint.
- Add step-up authentication for payout-account changes, 2FA changes, email changes, refunds, and account deletion.
- Add webhook replay protection and secret rotation.
- Add retention/deletion policies that preserve statutory finance/audit records while removing unnecessary personal data.
- Perform dependency, container, secret, and application security scans before launch.

---

# Part IV: recommended implementation order

## Phase 1: connect the product already designed

1. Typed frontend API client, access/refresh session model, role guards, and error envelope.
2. Build onboarding draft/status/complete APIs and align their schemas with every creator and brand question.
3. Connect existing auth, profile, campaigns, submissions, reviews, notifications, earnings, payouts, and funding endpoints.
4. Replace all fixtures and `localStorage` business state.
5. Add campaign membership endpoints so Joined is real.

## Phase 2: make identity and money safe

1. Refresh tokens, sessions, Google OIDC, password change, account deletion, and step-up authentication.
2. Live-shaped payment tests, brand ledger, refunds, server PDFs, and public receipt verification.
3. R2 multipart uploads, signed delivery, scanning, and media processing.
4. KYB customer application and operator queue.

## Phase 3: operate and support real customers

1. Support tickets and operator inbox.
2. Flagged-submission investigation, user/campaign controls, reconciliation, and job visibility.
3. Legal documents/acceptances, data export, and privacy workflows.
4. Monitoring, alerts, backups, incident runbooks, and audit export.

## Phase 4: remove manual product bottlenecks

1. Automated video/transcript/brief verification with evidence.
2. YouTube OAuth and metric ingestion.
3. Durable scheduling/queues and provider-degradation controls.
4. Push notifications if customer research shows they are needed.

---

# Part V: endpoint-to-screen ownership

| Product area | Existing endpoints to connect | New endpoints required |
|---|---|---|
| Auth screens | `/auth/signup`, `/login`, verification and recovery routes | Refresh, Google OIDC, real sessions, password change, 2FA, email change, account lifecycle |
| Creator onboarding | Existing all-at-once `PUT /creators/me/onboarding` and image upload | Creator onboarding GET, PATCH autosave, complete, reset, versioned options, schema/data migration |
| Creator settings | Creator profile, uploads, preferences, social routes, banks | Public profile/portfolio, handle/config support, KYC, security/session endpoints, production upload lifecycle |
| Creator campaigns | Campaign list/detail/rules/pool | Join, leave, joined-campaign list, source assets |
| Creator clips/verdicts | Submission create/list/detail/earnings/performance/appeal | Corrected resubmission and automated verifier internal contract if split into workers |
| Creator money | Earnings, banks, payout create/list/detail | Entry provenance, exports/statements, quote, server PDF, public receipt verification |
| Brand/individual onboarding | Existing all-at-once `PUT /organisations/me/onboarding` and image upload | Organisation onboarding GET, PATCH autosave, conditional completion, reset, versioned options, schema/data migration |
| Brand settings | Organisation profile/preferences | KYB application/status and document upload |
| Brand campaign studio | Complete campaign create/edit/rules/payout/funding | Resumable studio drafts, campaign source-asset lifecycle, finalized draft delete/duplicate |
| Brand campaign control | Stats, submissions, CSV report, pause/resume/close | Analytics time series, activity, closeout, refund status and server-generated financial documents |
| Brand money | Funding routes only | Organisation transaction ledger/detail/export, refunds, receipt PDFs |
| Notifications | Inbox/read routes | Unread count/archive; push only when enabled |
| Support and disputes | None | Help articles, customer/operator tickets, structured money/trust disputes and safety reports |
| Admin | Overview, payouts, funding, blocked earnings, job triggers, business override, audit | Operators/RBAC, users, creator KYC and brand KYB, flagged/random audits, campaign emergency controls, support/dispute/report queues, refunds, reconciliation, jobs, providers/webhooks, trust rules and audit detail |
| Legal | None | Versioned documents and acceptance records |

## Explicit non-goals for v1

These remain outside the PRD and should not expand the launch API unless product scope changes:

- content editing or creation tools;
- influencer discovery/search marketplace;
- payouts outside Nigeria;
- crypto/stablecoin settlement;
- multiple currencies;
- agency sub-accounts and complex organisation teams;
- native mobile-only APIs.

Fund, post, verify, pay, support, and operate are the production boundary.

---

# Part VI: all current frontend routes traced to APIs

This matrix covers every `page.tsx` currently under `frontend/app`. A dash means the page is intentionally static or only routes the user; it does not mean an API was forgotten.

## Landing, auth, and onboarding

| Frontend route | Reads | Mutations/actions |
|---|---|---|
| `/` | `GET /product-config` only if live platform/fee/legal copy is shown; the marketing composition can otherwise remain static. | No production mutation. The sample brief remains a local download and must clearly say it does not create/fund a campaign. |
| `/auth` | Optional `GET /auth/me` to redirect an existing session. | None. |
| `/auth/sign-up` | Optional `GET /auth/me`; `GET /legal/documents/{slug}` for current terms links. | Role selection is local; consent is recorded by `POST /legal/acceptances` during account creation/completion. |
| `/auth/sign-up/creator` | `GET /product-config`, legal documents as needed. | `POST /auth/signup` or Google OIDC start/callback; establish session. |
| `/auth/sign-up/organisation` | Same as creator signup. | `POST /auth/signup` or Google OIDC with organisation role intent. |
| `/auth/sign-in` | `GET /auth/providers` when showing available methods. | `POST /auth/login`, Google OIDC, and `POST /auth/2fa/challenge` when required. |
| `/auth/forgot-password` | None. | `POST /auth/forgot-password`. |
| `/auth/recovery-code` | None. | `POST /auth/recovery-code/verify`. |
| `/auth/reset-password` | None. | `POST /auth/reset-password`. |
| `/auth/verify-email` | `GET /auth/me` when session exists. | `POST /auth/verify-email`, `POST /auth/verify-email/resend`. |
| `/auth/success` | `GET /auth/me` to select role/onboarding/workspace destination. | None. |
| `/onboarding` | `GET /auth/me` and the role-specific onboarding GET to resume/redirect. | None beyond routing. |
| `/onboarding/creator` | `GET /onboarding/options`, `GET /creators/me/onboarding`. | `POST /uploads/images`, `PATCH /creators/me/onboarding` per screen, `DELETE .../draft`, `POST .../complete`. |
| `/onboarding/brand` | `GET /onboarding/options`, `GET /organisations/me/onboarding`. | `POST /uploads/images`, `PATCH /organisations/me/onboarding` per screen/branch, `DELETE .../draft`, `POST .../complete`. |

## Creator workspace

| Frontend route | Reads | Mutations/actions |
|---|---|---|
| `/dashboard` | `GET /creators/me/overview`, `GET /earnings/summary`, shell profile/notification count. | Notification read actions only when opened. |
| `/dashboard/campaigns` | `GET /campaigns` with search/feed/category/platform/cursor filters. | None. |
| `/dashboard/campaigns/[slug]` | `GET /campaigns/{ref}` including rules/pool/membership; `GET .../assets`; campaign-filtered leaderboard. | `POST /campaigns/{ref}/join`, `DELETE .../join`, `POST /reports` for safety reporting. |
| `/dashboard/campaigns/[slug]/submit` | Campaign detail, connected accounts, upload limits/config. | `POST /uploads/videos`, `POST /submissions`; reconnect platform via social OAuth when required. |
| `/dashboard/clips` | `GET /creators/me/clips` with status/cursor filters. | None. Each row opens its real submission ID. |
| `/dashboard/submissions/processing` | `GET /submissions/{id}` polling or revalidation. | Optional retry only through documented resubmission/reconnect paths; do not duplicate the original create request. |
| `/dashboard/submissions/approved` | `GET /submissions/{id}`, `GET .../earnings`, `GET .../performance`. | None. |
| `/dashboard/submissions/rejected` | Same submission/verdict reads. | `POST /submissions/{id}/resubmit`, `POST .../appeal`, or `POST /disputes` after ordinary appeal policy. |
| `/dashboard/submissions/appeal` | `GET /submissions/{id}` including appeal. | `POST /uploads/evidence`, `POST /submissions/{id}/appeal`, follow-up dispute only when eligible. |
| `/dashboard/earnings` | `GET /earnings/summary`, `GET /earnings/history`, optional `GET /earnings/entries/{id}`. | CSV/PDF exports. |
| `/dashboard/withdraw` | Earnings summary, payout destination, KYC status, `POST /payouts/quote`. | Step-up request/verify, then idempotent `POST /payouts`. |
| `/dashboard/payouts/receipt` | `GET /payouts/{id}`. | `GET /payouts/{id}/receipt.pdf`; dispute action when eligible. |
| `/dashboard/payout-account` | `GET /banks`, bank details, creator verification status. | Step-up, `POST /banks/resolve`, `PUT /creators/me/bank-details`, `POST .../verify`, optional delete. |
| `/dashboard/leaderboard` | `GET /leaderboard` with period/campaign/cursor. | None. |
| `/dashboard/notifications` | `GET /notifications`. | Read one/read all/archive. |
| `/dashboard/accounts` | `GET /creators/me/accounts` or `/social/accounts`. | OAuth login/callback, refresh/reconnect, disconnect, sync profile. |
| `/dashboard/settings` | Creator profile, preferences, accounts, bank details, KYC/public-profile state. | Profile save/photo upload, preference patch, social and bank actions. |
| `/dashboard/profile` | Own `GET /profiles/creators/{handle}` preview using the same public contract. | Copy URL locally; edits return to settings. |
| `/dashboard/security` | Auth providers, 2FA state, sessions. | Change/set password, 2FA setup/confirm/disable/recovery codes, revoke sessions, email change, export/delete account. |

## Brand workspace

| Frontend route | Reads | Mutations/actions |
|---|---|---|
| `/brand` | `GET /brand/overview`, notification count, organisation profile. | None beyond navigation. |
| `/brand/campaigns` | `GET /campaigns` with owner/status/cursor; `GET /campaign-drafts`. | Create, resume, duplicate, or delete allowed drafts. |
| `/brand/campaigns/new` | `GET /product-config`, `GET /campaign-drafts/{id}`. | `POST /campaign-drafts`, `PATCH` details/cover/source, image/asset upload. |
| `/brand/campaigns/new/brief` | Current campaign draft. | PATCH checklist changes with revision. |
| `/brand/campaigns/new/platforms` | Draft and enabled platform config. | PATCH platforms. Never advertise an unavailable adapter as ready. |
| `/brand/campaigns/new/rules` | Draft and product rule limits. | PATCH minimum, creator cap, explicit duration-versus-pot end condition. |
| `/brand/campaigns/new/budget` | Draft and fee/limit config. | PATCH decimal pot/rate; server recalculates expected views. |
| `/brand/campaigns/new/review` | Canonical draft plus validation blockers. | `POST /campaign-drafts/{id}/finalize`. |
| `/brand/campaigns/new/fund` | Campaign, server funding quote, and `GET /campaigns/{ref}/funding` when an order exists. | `POST .../funding`, redirect to hosted checkout or show collection account, `POST .../confirm`, cancel unpaid order. |
| `/brand/campaigns/new/funded` | Campaign and confirmed funding order. | Download funding receipt; no client-side fake confirmation. |
| `/brand/campaigns/[slug]` | Campaign, stats, analytics, assets, submissions, activity. | Pause/resume, authorised close, report export, safety/dispute actions. |
| `/brand/campaigns/[slug]/report` | `GET .../closeout`, transactions/refund state as needed. | CSV report, closeout PDF, transaction receipt download. |
| `/brand/reviews` | `GET /brand/reviews` with tab/cursor filters. | Assignment is admin-only; brand chooses a row. |
| `/brand/reviews/[id]` | `GET /brand/reviews/{submission_id}` and signed evidence media. | Approve or request correction; decision must be idempotent/concurrency-safe. |
| `/brand/transactions` | Organisation ledger summary/list. | CSV statement export and row selection. |
| `/brand/transactions/[id]` | Transaction detail. | Server receipt PDF and eligible dispute action. |
| `/brand/notifications` | Notification inbox. | Read one/read all/archive. |
| `/brand/settings` | Organisation profile/preferences, KYB state, finance email, auth security link. | Profile/logo save, finance-email verification, preference patch, KYB submission. |

## Framework and fallback routes

| Frontend route | Reads | Mutations/actions |
|---|---|---|
| Next.js not-found boundary | None. | None. It must not mask API authorization or provider errors as generic 404s. |

---

# Part VII: unmounted experimental endpoints in the repository

The following 38 Flask routes live under `backend/service-test/`. They are isolated provider experiments, are **not included by `backend/main.py`**, are not part of the 101-route production application count, and must not be deployed on the public Clippit API. Their tested logic should live behind the production provider adapters instead.

| Experimental service | Routes present in the experiment |
|---|---|
| TikTok | `GET /`, `GET /login`, `GET /callback`, `GET /logout`, `GET /api/status`, `GET /api/videos` |
| Instagram | `GET /`, `GET /login`, `GET /callback`, `GET /logout`, `GET /api/status`, `GET /api/media`, `GET /api/insights` |
| Facebook | `GET /`, `GET /login`, `GET /callback`, `GET /select-page/{page_id}`, `GET /logout`, `GET /api/status`, `GET /api/posts`, `GET /api/page-insights` |
| Threads | `GET /`, `GET /login`, `GET /callback`, `GET /logout`, `GET /api/status`, `GET /api/threads`, `GET /api/user-insights` |
| X | `GET /`, `GET /login`, `GET /callback`, `POST /api/dev-connect`, `GET /logout`, `GET /api/config`, `GET /api/status`, `GET /api/posts`, `GET /api/verify`, `GET /api/replies` |

`POST /api/dev-connect` is explicitly development-only and must never be copied into the production authentication surface.

---

# Part VIII: PRD invariant traceability

| PRD requirement or invariant | API/service contract that owns it |
|---|---|
| Brand creates campaign details and optional source material | Campaign-studio draft lifecycle, campaign create/update, source-asset lifecycle |
| Brief is a checklist, not an opaque paragraph | Existing campaign rules GET/PUT; draft PATCH; requirement-level submission results |
| Brand chooses supported platforms | Product config plus campaign draft/final campaign validation |
| Brand sets pot and rate; expected views are derived | Draft PATCH, campaign create/payout rule, funding quote; decimal server calculation |
| Minimum views, creator cap, optional deadline/pot-only close | Payout-rule endpoint and explicit end-condition correction; earnings service invariants |
| Campaign opens only after funds clear | Existing funding create/read/confirm plus signed payment webhook |
| Creator browses open campaigns with rate/pot/rules visible | Existing campaign list/detail/rules/pool with creator-safe visibility |
| Creator joins before submitting | New join/leave/list-membership endpoints |
| Connected social account is required to earn | Existing social/account endpoints plus submission validation and token lifecycle |
| Creator submits public link and original file | Existing upload video and submission create; production multipart media lifecycle |
| Verdict includes requirement-level reasons | Existing submission detail and review endpoints; automated verifier contracts |
| Creator can appeal a rejection | Existing appeal; escalated dispute endpoints preserve a second-level process |
| Views always come from a platform, never a human field | Internal metrics registration/polling, append-only snapshots, no customer write endpoint for views |
| Approved clips are polled on schedule | Intelligence tracking routes, durable scheduler, provider adapters |
| Fraud signals flag suspicious growth | Existing trust result/review, new flagged/random audit queues and versioned rule management |
| Earnings accrue but are held for five days | Existing earnings settlement and product config; immutable entry/provenance detail |
| Partial thousands do not pay | Existing whole-thousand cumulative settlement rule; exposed in campaign and earning detail |
| No clip/creator exceeds caps | Existing payout-rule and row-locked settlement; admin provenance view |
| Campaign never pays more than its pot | Existing row-locked hard ceiling, pool endpoint, unified ledger/reconciliation |
| Pot visibly drains | Existing pool/stats plus new analytics time series |
| Campaign closes at empty pot, deadline, or authorised close | Existing close/sweep; explicit budget-only end semantics; closeout/refund contracts |
| Payable money reaches a Nigerian bank | Banks, bank verification, creator KYC, payout quote/create/status/webhook/reconciliation |
| Every naira traces to a platform snapshot | Earning-entry detail, payout provenance, ledger, audit, receipt verification |
| Brand sees live submissions, views, spend and closeout | Existing stats/submissions/report plus analytics/activity/closeout/transactions |
| Admin sees flagged submissions | Flagged/global queues, investigation detail, trust decisions, earnings holds, random audits |
| Support can resolve customer issues without silently editing history | Tickets, disputes, reports, operator RBAC, domain commands, audit log |
