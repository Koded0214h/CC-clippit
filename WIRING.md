# Clippit API Wiring Audit

Audit date: 23 September 2026. Source of truth: the live FastAPI OpenAPI
document at `http://localhost:8000/openapi.json` and a static inspection of
the frontend. The live document has **203 operations**.

## Status definitions

| Status | Meaning |
|---|---|
| Fully connected | Typed frontend client, consumed by a real screen/action, and the existing mock stays as its empty/error fallback. |
| Partial | A client/screen exists but a write failure is hidden, a route is not data-driven end-to-end, or only part of the experience is connected. |
| Client only | A typed function exists but no frontend screen invokes it. |
| No client | No typed frontend function or real frontend usage exists. |
| Internal | Service-to-service endpoint; intentionally not exposed to the browser. |

## Fully connected operations

| Experience | Live operations | Frontend owner |
|---|---|---|
| Account registration and recovery | `POST /auth/signup`, `/auth/login`, `/auth/logout`, `/auth/refresh`, `/auth/verify-email`, `/auth/verify-email/resend`, `/auth/forgot-password`, `/auth/recovery-code/verify`, `/auth/reset-password` | `AuthPages.tsx`, `user-context.tsx` |
| Account security and deletion | `POST /auth/change-password`, `GET /auth/sessions`, `DELETE /auth/sessions/{session_id}`, `DELETE /auth/sessions/others`, `POST /auth/step-up/request`, `/auth/step-up/verify`, `DELETE /auth/account` | Customer security/account screens |
| Creator home and discovery | `GET /creators/me/overview`, `/creators/me/clips`, `/campaigns`, `/campaigns/{campaign_ref}`, `/campaigns/{campaign_ref}/stats`, `/campaigns/{campaign_ref}/submissions`, `/leaderboard` | Dashboard and brand campaign screens |
| Creator earnings | `GET /earnings/summary`, `/earnings/history` | Creator earnings and withdrawal screens |
| Creator profile and preferences | `GET|PUT /creators/me/profile`, `GET|PATCH /profile/preferences` | Dashboard settings |
| Connected accounts | `GET /social/accounts`, `DELETE /social/{platform}` | Creator connected-accounts screen |
| Bank account setup | `GET /banks`, `POST /banks/resolve`, `GET|PUT /creators/me/bank-details` | Payout-account screen |
| Brand overview and reviews | `GET /brand/overview`, `GET /brand/reviews`, `GET /brand/reviews/{submission_id}`, `POST /brand/reviews/{submission_id}/approve`, `POST /brand/reviews/{submission_id}/request-correction` | Brand screens |
| Brand identity and alerts | `GET|PUT /organisations/me/profile`, `GET|PATCH /profile/preferences` | Brand settings |
| Notifications | `GET /notifications`, `GET /notifications/unread-count`, `POST /notifications/read-all` | Customer notifications and shell badges |
| Admin command centre and queues | `POST /auth/login`, `GET /admin/overview`, `/admin/users`, `/admin/campaigns`, `/admin/submissions`, `/admin/support/tickets`, `/admin/disputes`, `/admin/payouts` | `AdminScreens.tsx` |

The fully connected screens retain their original fixture data. Real data is
used only after a successful non-empty response; empty/error responses keep
the designed fallback state.

## Partial operations

| Operation | Why it is partial |
|---|---|
| `POST /submissions`, `POST /submissions/{submission_id}/resubmit` | Submit-clip screen invokes the API, but currently advances through the mock success flow if the API rejects the request. |
| `GET /campaigns/{campaign_ref}` on submit-clip | Campaign metadata is live, but video upload is not sent to `POST /uploads/videos` before submission. |
| `POST /creators/me/bank-details/verify` | Typed client exists; the payout-account experience does not invoke verification. |

## Typed client exists, but no screen consumes it

| Area | Operations not currently consumed by a frontend experience |
|---|---|
| Admin finance and moderation | `GET /admin/payouts` detail/actions, funding list/confirm, blocked earnings, settle, sweep, business verification, audit, user detail/suspend/restore, submission detail/trust actions/flagged/random audits, campaign detail/pause/close, earnings list/detail/hold/release, ledger list/detail, operators/invite/update/suspend/restore, trust rules, provider health, all admin ticket detail/update/reply/note actions, all admin dispute detail/update/resolve/reopen actions, and all admin reports operations. |
| Payouts | `POST /payouts`, `GET /payouts`, `GET /payouts/{payout_id}`. The withdrawal and receipt UI still use local state/mock receipt data. |
| Submissions | `GET /submissions`, `/submissions/{submission_id}`, `/earnings`, `/performance`; `POST /appeal`, `/withdraw`. |
| Notifications | `POST /notifications/{notification_id}/read` and `/archive`. |
| Campaign membership | `POST|DELETE /campaigns/{campaign_ref}/join`. |

## No typed frontend client or real screen wiring

| Backend area | Operations |
|---|---|
| Auth / identity | `GET /auth/me`, `/auth/permissions`, `/auth/providers`, Google login/link/callback/unlink, first-password, and admin-invitation status/acceptance. |
| Campaign authoring and lifecycle | All `GET|POST|PATCH|DELETE /campaign-drafts*`; `POST /campaigns`; `PATCH /campaigns/{campaign_ref}`; activate, close, pause, resume; payout-rule; pool; rules; report. |
| Campaign funding and refunds | All `/campaigns/{campaign_ref}/funding*` and `/campaigns/{campaign_ref}/refunds*` operations. |
| Creator and organisation onboarding | All `/creators/me/onboarding*` and `/organisations/me/onboarding*` operations; `GET /creators/me/accounts`; `GET /creators/{creator_id}/bank-details`; organisation transaction list/detail. |
| Customer support | All `GET|POST /support/tickets*` operations. Current support pages are fixture/local-storage experiences. |
| Customer disputes | All `GET|POST /disputes*` operations. Current dispute pages are fixture/local-storage experiences. |
| Legal, reports, receipts and public product | All `/legal/*`, `/reports*`, `/receipts/{reference}/verify`, `/product-config`, `/handles/{handle}/availability`, `/profiles/creators/*`, and `/profiles/organisations/*` operations. |
| Uploads and push | `POST /uploads/evidence`, `/uploads/images`, `/uploads/videos`; `POST|DELETE /push-subscriptions*`. |
| Social OAuth | `GET /social/{platform}/login` and `/callback`. The account screen can list/disconnect but cannot start a real connection. |

## Intentionally browser-unwired internal operations

`GET /health`; every `/internal/*` endpoint (social tokens, internal users,
performance/tracking/trust, and trust rules). These are service or deployment
contracts and must not be called directly by the browser.

## Frontend experiences with no matching usable endpoint

| Experience | Finding |
|---|---|
| Admin KYC / creator verification | No admin KYC queue, detail, or decision operation exists in the live specification. |
| Admin KYB / business verification queue | Business verification write exists, but no admin organisation/KYB queue or detail read contract exists. |
| Admin refunds queue/detail | No global admin refund queue/detail/action contract exists; only campaign-scoped refund operations exist. |
| Admin risk cases | No admin risk-case queue, detail, or action contract exists. |
| Admin webhooks and delivery monitor | No webhook/delivery monitoring endpoint exists. |
| Admin roles and runtime controls | No role-matrix or system-maintenance configuration endpoint exists. |
| Support/help content | No help-centre/article API exists. |

## Known contract defect fixed during this audit

`frontend/lib/api/brand.ts` now calls the live correction endpoint:
`POST /brand/reviews/{submission_id}/request-correction`.

## Verification

- `npm run typecheck` passes.
- Backend `compileall` passes.
- `GET /health` returns `{"status":"ok"}`.
- Swagger UI responds at `http://localhost:8000/docs`.
- A production frontend build did not complete in this environment, so it is
  not marked as verified.
