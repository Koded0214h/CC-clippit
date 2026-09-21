# Clippit production API inventory and gap register

Last audited: 2026-09-21

This document is the backend contract for taking Clippit from the current reviewable product to a production service for creators, brands, support staff, finance operators, trust and safety, and administrators.

It has four jobs:

1. Record every endpoint currently mounted by `backend/main.py`.
2. Distinguish code that exists from code that is genuinely launch-ready.
3. Define the endpoints still missing from the customer and operator journeys.
4. Identify production work that cannot be solved by adding an endpoint.

The inventory was produced from the FastAPI routers themselves, not from the older README count. There are currently **97 mounted routes**, including hidden webhook/media routes and internal service routes.

The audited target adds **94 definite routes**: **55 P0 launch blockers** and **39 P1 broad-production routes**. It also defines **4 conditional internal routes** for the recommended separate verification/media workers. That produces a maximum target surface of **195 routes**. This does not mean 98 unrelated systems need to be written: many of the new routes are thin, permissioned views or actions over shared session, ledger, support, verification, and moderation services.

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

## System

| Method and path | Access | What it does | Status |
|---|---|---|---|
| `GET /health` | Public | Returns a shallow process-health response. It does not prove database, storage, provider, queue, or worker readiness. | Built |

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

## Creator profile, onboarding, bank destination, and workspace

| Method and path | Access | Request / result | Status |
|---|---|---|---|
| `PUT /creators/me/bank-details` | Creator | Saves bank code/name/account number and resets verification whenever details are submitted. | Built |
| `GET /creators/me/bank-details` | Creator | Returns the creator's masked payout destination and verification state. | Built |
| `GET /creators/{creator_id}/bank-details` | Admin only | Returns a creator's masked bank details for a support/dispute case. | Built; keep admin-only and audit every read before launch |
| `GET /creators/me/profile` | Creator | Returns editable creator identity, bio, photo, interests, intended platforms, discovery source, experience, goals, and onboarding state. | Built |
| `PUT /creators/me/profile` | Creator | Replaces editable creator profile fields after ownership-checking the photo upload. | Built |
| `PUT /creators/me/onboarding` | Creator | Completes creator onboarding and stores the onboarding answers. | Built |
| `GET /creators/me/clips` | Creator | Returns creator submission totals and clip rows with status, verified views, and earnings. | Built |
| `GET /creators/me/accounts` | Creator | Returns every supported platform, connection state, handle, and last reading time. | Built, dependency pending for YouTube |
| `GET /creators/me/overview` | Creator | Returns dashboard campaign recommendations and earnings summary. | Built |

## Organisation profile and onboarding

| Method and path | Access | Request / result | Status |
|---|---|---|---|
| `GET /organisations/me/profile` | Organisation | Returns organisation identity, description, logo, finance contact, workflow data, and verification state. | Built |
| `PUT /organisations/me/profile` | Organisation | Updates editable organisation fields; business verification itself remains admin-controlled. | Built |
| `PUT /organisations/me/onboarding` | Organisation | Completes the brand/individual onboarding branch and stores the answers. | Built |

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
| Missing P1 | `POST /auth/2fa/setup` | Create a pending TOTP secret and return an `otpauth` URI/QR payload without enabling 2FA yet. |
| Missing P1 | `POST /auth/2fa/confirm` | Verify the first TOTP, enable 2FA, and return one-time recovery codes. |
| Missing P1 | `POST /auth/2fa/challenge` | Complete a login or sensitive-action challenge with TOTP or one recovery code. |
| Missing P1 | `DELETE /auth/2fa` | Disable 2FA after password/recent step-up verification. |
| Missing P1 | `POST /auth/2fa/recovery-codes/regenerate` | Invalidate old recovery codes and issue a new one-time set after step-up verification. |
| Missing P1 | `POST /auth/email-change/request` | Verify the password/step-up state and send codes to old and new addresses. |
| Missing P1 | `POST /auth/email-change/confirm` | Consume both proofs, change the email, audit the change, and notify the old address. |
| Missing P1 | `POST /auth/account-export` | Queue a privacy export containing profile, campaigns/submissions, ledger, and audit-visible customer data; return a job ID. |
| Missing P0 | `DELETE /auth/account` | Re-authenticate, apply legal/ledger retention rules, revoke sessions/tokens, disconnect socials, and schedule deletion/anonymisation. Refuse unsafe deletion while money is unsettled. |
| Missing P1 | `GET /auth/account-export/{job_id}` | Return export status and a short-lived download URL when ready. |

## C. Social-token lifecycle, provider compliance, and YouTube

| Priority | Method and path | Required contract |
|---|---|---|
| Missing P0 | `POST /social/{platform}/refresh` | Refresh an expiring provider token when supported; update encrypted credentials atomically and surface `reconnect_required` when refresh is impossible. This may normally be called by a worker rather than the browser. |
| Missing P1 | `POST /social/{platform}/sync-profile` | Re-read the connected handle/display name and connection health after permission changes. |
| Missing P0 | `POST /webhooks/social/{platform}/deauthorize` | Verify the provider request and disconnect/revoke the affected account when a user removes Clippit at the platform. |
| Missing P0 | `POST /webhooks/social/{platform}/data-deletion` | Satisfy Meta/platform data-deletion callbacks and return the required confirmation/status reference. |

No new public path is needed for YouTube because the generic login/callback and account-list paths already exist. The missing work is a YouTube OAuth provider, token refresh, channel identity, video lookup/metrics adapter, quota handling, ingestion tests, and enabling `connectable` only after those pass.

## D. Creator participation in campaigns

The PRD explicitly says a creator joins a campaign. The current API infers participation only after submission, which cannot correctly power Joined filters, capacity rules, or pre-submission campaign updates.

| Priority | Method and path | Required contract |
|---|---|---|
| Missing P0 | `POST /campaigns/{campaign_ref}/join` | Join an open campaign after checking role, required connected account, capacity/caps, campaign state, and duplicate membership. Idempotent. |
| Missing P0 | `DELETE /campaigns/{campaign_ref}/join` | Leave before an accepted submission exists; preserve historical membership and refuse invalid withdrawal after earning begins. |
| Missing P0 | `GET /creators/me/campaigns` | List joined, submitted, active, completed, and left campaigns with cursor pagination. |
| Missing P1 | `DELETE /campaigns/{campaign_ref}` | Permanently delete an unfunded draft owned by the organisation. Refuse once funding or submissions exist. |
| Missing P1 | `POST /campaigns/{campaign_ref}/duplicate` | Copy an owned campaign into a new unfunded draft without copying transactions, submissions, dates, or provider references. |

Campaign editing does not need a new endpoint: `PATCH /campaigns/{campaign_ref}`, `PUT .../rules`, and `PUT .../payout-rule` already cover it.

## E. Brand ledger, refunds, statements, official receipts, and public verification

The frontend currently fabricates brand transactions and prints client-rendered receipts. Official financial records must come from the server-side ledger.

| Priority | Method and path | Required contract |
|---|---|---|
| Missing P0 | `GET /organisations/me/transactions` | Cursor-paginated ledger of funding, fees, creator allocations, refunds, and adjustments with filters for campaign, type, status, and date. |
| Missing P0 | `GET /organisations/me/transactions/{transaction_id}` | Return one authorised immutable ledger item with sender, recipient, provider references, amount, currency, campaign, and audit-safe provenance. |
| Missing P1 | `GET /organisations/me/transactions/export` | Export a date-filtered CSV statement using formula-injection-safe cells. |
| Missing P0 | `POST /campaigns/{campaign_ref}/refunds` | Create an idempotent refund of the legally refundable unused balance after close/cancellation and provider reconciliation. |
| Missing P0 | `GET /campaigns/{campaign_ref}/refunds` | Return refund amount, status, destination, provider reference, timestamps, and failure reason. |
| Missing P1 | `POST /payouts/quote` | Validate amount and destination and return fee, net amount, currency, and quote expiry without reserving money. |
| Missing P0 | `GET /payouts/{payout_id}/receipt.pdf` | Generate the creator's official one-page PDF from immutable server data, with a page-level watermark and verification code. |
| Missing P0 | `GET /organisations/me/transactions/{transaction_id}/receipt.pdf` | Generate the brand's official one-page transaction PDF from the ledger. |
| Missing P0 | `GET /campaigns/{campaign_ref}/funding/receipt.pdf` | Generate the official funding order/certificate PDF from provider-confirmed data. |
| Missing P0 | `GET /receipts/{reference}/verify` | Public, rate-limited verification response containing safe amount/status/date/type/issuer facts and a signed-document digest; never expose private bank or account data. |
| Missing P1 | `POST /admin/refunds/{refund_id}/retry` | Re-drive a retryable provider refund idempotently and audit the operator. |
| Missing P1 | `POST /admin/refunds/{refund_id}/fail` | Finalise an unrecoverable refund failure with an operator reason and escalation state. |

## F. Support centre and customer tickets

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

## G. Business verification/KYB

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

The existing `POST /admin/organisations/{user_id}/verify-business` should become an audited emergency override, not the normal verification workflow.

## H. Admin users, campaigns, moderation, trust, and fraud

The PRD explicitly requires a flagged-submissions queue. Current admin endpoints expose counts and blocked earnings but not an operable investigation queue.

| Priority | Method and path | Required contract |
|---|---|---|
| Missing P0 | `GET /admin/users` | Search/filter creators, organisations, and admins by state, verification, risk, creation date, and recent activity. |
| Missing P0 | `GET /admin/users/{user_id}` | Return safe identity/profile, verification, sessions summary, connected-platform health, money summary, sanctions, and audit timeline. |
| Missing P0 | `POST /admin/users/{user_id}/suspend` | Suspend access/earning/funding with scope, reason, duration, and customer notification. Never delete ledger history. |
| Missing P0 | `POST /admin/users/{user_id}/restore` | Restore a suspended account after recording reason and operator. |
| Missing P1 | `POST /admin/users/{user_id}/force-logout` | Revoke all sessions for a compromised account and notify the customer. |
| Missing P0 | `GET /admin/submissions/flagged` | Paginated flagged-submission queue with platform, campaign, creator, risk rule, severity, amount at risk, age, and assignment. |
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
| Missing P1 | `GET /admin/audit/{event_id}` | Return one full audit event with request/provider correlation fields. |
| Missing P1 | `GET /admin/audit/export` | Export filtered audit data for an incident or finance review with strict permissions. |
| Missing P1 | `GET /admin/jobs` | Return scheduled-job last run, next run, lease owner, duration, processed count, and last error. |
| Missing P1 | `POST /admin/jobs/{job_name}/run` | Run one allowlisted job with an idempotency key and audit record. This supersedes one-off settle/sweep buttons over time. |

## I. Production media lifecycle

The existing streaming upload routes are acceptable for development and small pilots. Large creator videos should not pass through a single web worker in production.

| Priority | Method and path | Required contract |
|---|---|---|
| Missing P0 | `POST /uploads/multipart` | Create an owned R2 multipart upload after validating intended kind, filename, declared size, and content type; return short-lived signed part URLs. |
| Missing P0 | `POST /uploads/multipart/{upload_id}/complete` | Verify uploaded parts, size, byte signature, checksum, and ownership; queue scan/transcode/thumbnail work. |
| Missing P1 | `GET /uploads/{upload_id}` | Return owner-safe metadata and processing/scan state, plus a short-lived signed read URL when allowed. |
| Missing P1 | `DELETE /uploads/{upload_id}` | Delete an unattached owned upload or schedule deletion under retention rules. Refuse deletion when referenced by immutable evidence/finance records. |
| Missing P1 | `POST /uploads/support-attachments` | Upload ticket attachments under support-specific type, size, scanning, and access rules. This may reuse the multipart implementation. |

`GET /media/{key:path}` must be disabled in production once signed R2 delivery is active.

## J. Notification delivery beyond the inbox

| Priority | Method and path | Required contract |
|---|---|---|
| Missing P1 | `GET /notifications/unread-count` | Cheap shell badge count without downloading the full inbox. |
| Missing P1 | `POST /notifications/{notification_id}/archive` | Hide one owned notification while preserving the audit/event record. |
| Missing P1 | `POST /push-subscriptions` | Register/update a browser push subscription for the current session and preference state. |
| Missing P1 | `DELETE /push-subscriptions/{subscription_id}` | Remove one owned push subscription on logout, revocation, or browser unsubscribe. |

Push can be deferred during a controlled pilot if in-app and transactional email delivery are operational.

## K. Legal documents and consent records

The frontend currently links to `/terms` and `/privacy`, but those pages do not exist. The pages may be statically rendered; the acceptance record still belongs in the backend.

| Priority | Method and path | Required contract |
|---|---|---|
| Missing P0 | `GET /legal/documents/{slug}` | Return the currently published Terms, Privacy Policy, Community Rules, or campaign-funding terms with immutable version and effective date. A static frontend can consume this at build time. |
| Missing P0 | `POST /legal/acceptances` | Record user, document/version, accepted time, IP/user-agent hash, and the action that required consent. Idempotent per version. |
| Missing P1 | `GET /legal/acceptances/me` | Return the caller's accepted versions and any newly required consent. |

## L. Automated brief verification and media processing

These are internal contracts. They are needed only if verification/transcoding run outside the FastAPI process, which is the recommended production topology.

| Priority | Method and path | Required contract |
|---|---|---|
| Conditional P0 | `POST /internal/submissions/{submission_id}/verification/start` | Idempotently enqueue transcription, frame sampling, brief checks, and decision aggregation. |
| Conditional P0 | `GET /internal/submissions/{submission_id}/verification` | Return internal stage state, attempts, model/provider versions, safe failure codes, and resulting requirement checks. |
| Conditional P0 | `POST /internal/submissions/{submission_id}/verification/callback` | Signed worker callback that stores requirement-level evidence and the final verifier decision exactly once. |
| Conditional P1 | `POST /internal/uploads/{upload_id}/processed` | Signed media-worker callback for scan, duration, dimensions, normalized video, waveform, and thumbnail assets. |

If these jobs remain in-process, expose no extra HTTP routes; call the same service functions directly. The product still needs the worker behavior, retries, dead-letter queue, and audit data.

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
2. Existing auth, onboarding, profile, campaigns, submissions, reviews, notifications, earnings, payouts, and funding endpoints.
3. Replace all fixtures and `localStorage` business state.
4. Add campaign membership endpoints so Joined is real.

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
| Creator onboarding/settings | Creator profile/onboarding, uploads, preferences, social routes, banks | Documented security/session endpoints and production upload lifecycle |
| Creator campaigns | Campaign list/detail/rules/pool | Join, leave, joined-campaign list |
| Creator clips/verdicts | Submission create/list/detail/earnings/performance/appeal | Automated verifier internal contract if split into workers |
| Creator money | Earnings, banks, payout create/list/detail | Quote, server PDF, public receipt verification |
| Brand onboarding/settings | Organisation profile/onboarding | KYB application/status and document upload |
| Brand campaign studio | Campaign create/edit/rules/payout/funding | Draft delete/duplicate; no separate edit endpoint is needed |
| Brand campaign control | Stats, submissions, report, pause/resume/close | Refund status and server-generated financial documents |
| Brand money | Funding routes only | Organisation transaction ledger/detail/export, refunds, receipt PDFs |
| Notifications | Inbox/read routes | Unread count/archive; push only when enabled |
| Support | None | Entire support article/ticket/operator API |
| Admin | Overview, payouts, funding, blocked earnings, job triggers, business override, audit | Users, flagged submissions, campaign emergency controls, KYB queue, support queue, refunds, reconciliation, job/audit detail |
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
