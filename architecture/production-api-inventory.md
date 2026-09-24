# Clippit V1 API inventory and PRD compliance register

Last reconciled: 2026-09-24

Authoritative product source: `Clippit_Product_Requirements_Document_V1.0.pdf`, 16 pages, September 2026

Repository baseline: commit `88c675b`

This document is the API build contract for the Clippit V1 product. It translates the locked product behavior in the V1 PRD into API responsibilities and records whether the current backend satisfies them.

The V1 PRD supersedes the earlier high-level PRD where they conflict. Requirements from the older document, previous screen explorations, or implementation preferences are not V1 requirements unless the V1 PRD states them.

## Reading rules

- **Required behavior** is copied or directly derived from locked V1 behavior.
- Endpoint paths are the repository's API contract for delivering that behavior; the PRD itself does not prescribe URL names.
- Where the PRD says **TBD**, this document preserves the decision as TBD. It must not invent a provider, role hierarchy, fraud threshold, polling cadence, or recovery policy.
- A route existing in code does not make the behavior compliant. The status applies to the complete PRD contract behind it.
- Extra endpoints may remain in the application, but they are not V1 acceptance blockers unless listed here.
- Raw route count is not a completion metric. V1 acceptance is based on the behaviors and invariants in this document.

## Status labels

| Status | Meaning |
|---|---|
| **Compliant** | The current backend route and domain behavior satisfy the V1 requirement. Live-provider approval or deployment configuration may still be needed. |
| **Partial** | A route or service exists, but required V1 behavior, state, provenance, or enforcement is incomplete or contradictory. |
| **Missing** | No usable backend contract currently delivers the requirement. |
| **TBD** | The PRD intentionally leaves the named provider or narrow policy undecided. Do not implement an invented product rule. |
| **Supporting** | Useful implementation/API behavior that is not itself a V1 product requirement. |

---

# 1. Locked V1 product decisions

These values are product constants, not implementation options.

| Decision | Locked V1 behavior |
|---|---|
| Supported social platforms | Instagram, TikTok, Facebook, X (Twitter), and YouTube only |
| Submission input | Creator submits the live social URL only; the product must not require a second manual video upload |
| Media retrieval | `yt-dlp` retrieves the posted media for compliance analysis |
| Compliance model | `Qwen3.8-Omni-Flash`, using the real video and its audio where possible |
| Payable view source | Official APIs for the five supported platforms only; never creator-entered views |
| Payments | Paystack |
| Initial campaign fee | 15% of the initial creator pot; non-refundable |
| Campaign top-up fee | 2.5% of the amount added |
| Manual cancellation fee | 2.5% of the refundable unused balance, after creator obligations are protected |
| Creator wallet withdrawal fee | 7% of the creator's requested gross withdrawal |
| Brand wallet withdrawal fee | 7% of the Brand's requested gross withdrawal |
| Minimum wallet withdrawal | NGN 5,000 |
| Minimum campaign earning threshold | At least 1,000 official verified views; a Brand may set a higher value, never a lower one |
| Review window | Five days after Qwen approval at the submission level |
| Account model | Creator and Brand are separate account types; no one-click role switching |
| Brand types | Individual Brand and Company Brand |
| Campaign access | Public or invite-code |
| Pause behavior | Acquisition-only pause or full earning freeze |
| Leaderboards | Global, Country, and Campaign; rankable by verified views or valid earnings |

Threads is not a supported V1 platform. Existing Threads code may remain dormant, but product configuration, campaign validation, connection UI, and submission validation must expose only the five locked platforms.

---

# 2. Cross-cutting invariants

Every relevant route and background process must preserve these rules.

## 2.1 Identity and authority

- Creator and Brand accounts remain separate. No API may mutate one account into the other or expose a role-switch action.
- Company Brands support teammates and permission checks for funding, withdrawals, cancellation, Qwen overrides, team management, and campaign editing.
- Exact Company role names and the final permission matrix are **TBD**. APIs must use stored permissions/capabilities rather than hard-coded invented role names.
- The Brand has final authority over campaign-specific content compliance for its own campaign.
- Admin retains platform-wide authority for fraud, abuse, enforcement, account restriction, and campaign removal.
- Every Brand/Admin verdict override records actor, prior verdict, new verdict, reason, and timestamp.

## 2.2 Money and ledger

- Brand and Creator balances are projections of immutable ledger entries, never editable balance fields.
- A campaign pot is a reserved Brand-wallet balance and is not freely withdrawable while allocated.
- No campaign allocation can make the pot negative.
- If the next valid earning exceeds the remaining pot, allocate only the remaining amount.
- Creator earnings already validly recognized or reserved are protected before any Brand refund is calculated.
- The initial 15% campaign fee is never refunded.
- The 2.5% cancellation fee applies only to a Brand-initiated manual early end and only to the refundable unused remainder.
- Natural end with unused money returns that unused balance to the Brand wallet without the manual-cancellation fee.
- Top-ups add pot only; they never change the immutable payout rate or content rules.
- Clippit absorbs Paystack and other system costs. No extra pass-through provider fee may appear in customer contracts.
- Money-moving commands must be transactionally safe and idempotent so retries cannot collect, reserve, refund, or transfer twice.

## 2.3 Submission, review, and earnings

- A submission is a URL for a post on one supported platform and must belong to the submitting Creator's connected account.
- Retrieval/model failure is a technical state. It must never become an automatic content rejection.
- Every Qwen result contains an overall verdict, one result per campaign rule, evidence, timestamps where possible, confidence, and a human-review reason when uncertain.
- Qwen approval starts one five-day review window for the submission.
- Official views are tracked immediately during that window; calculated earnings remain held/provisional.
- If no valid in-window rejection occurs, the held amount becomes recognized/available and subsequent valid earnings continue normally. The backend must not create a new five-day product review window for every later view accrual.
- A valid Brand rejection inside the window prevents unrecognized held amounts from becoming withdrawable.
- A Brand rejection after the window stops future earnings but cannot claw back already recognized earnings.
- AI rejection, Brand/human rejection, and fraud enforcement expose an appeal path where applicable.
- Appeal history preserves the original decision and evidence, appeal content/evidence, reviewer, and final outcome.

## 2.4 Views and ranking

- Payable views come only from official Instagram, TikTok, Facebook, X, and YouTube APIs.
- Every view reading is timestamped and retained with source/reference metadata sufficient to reconstruct earnings.
- No customer or operator endpoint accepts a payable view count.
- Only complete thousands pay: 4,900 eligible views are billed as 4,000.
- Per-video and per-creator caps are enforced before new earnings are recognized.
- Global, Country, and Campaign leaderboards support ranking by verified views and by valid earnings.
- Country is the only local scope in V1. No state or city leaderboard is required.

## 2.5 Audit and explainability

For every naira earned and every content rejection, stored records must reconstruct:

- the campaign, immutable rate, applicable cap, and pot balance before/after;
- the official platform reading and complete-thousand increment used;
- the Qwen model/version and rule-by-rule result, or the human decision;
- the hold/recognized/available state transition;
- the ledger entries that reserved, moved, refunded, or paid the money;
- every Brand/Admin override and appeal outcome;
- notification event, recipient, channel, delivery state, and timestamps.

---

# 3. Accounts, authentication, verification, and social connection

## 3.1 Accounts and sessions

| Method and path | Status | Required V1 contract |
|---|---|---|
| `POST /auth/signup` | **Partial** | Create a separate Creator or Brand account. Brand signup/onboarding must classify the account as Individual or Company. Current auth has `creator`/`organisation` but no persisted Brand subtype. |
| `POST /auth/login` | **Compliant** | Authenticate the selected account. Admin may use the same secure credential flow. |
| `POST /auth/logout` | **Compliant** | End the current authenticated session. |
| `GET /auth/me` | **Partial** | Return account type, Brand subtype where applicable, onboarding state, KYC/KYB state, and effective Company permissions. Current response lacks Brand subtype, KYC/KYB, and Company permissions. |
| No role-switch endpoint | **Compliant** | Creator and Brand identities remain separate; do not add a one-click role switch. |

Refresh tokens, password recovery, session/device management, Google sign-in, 2FA, email change, and account export may be useful security/product features, but the V1 PRD does not make their particular endpoints acceptance requirements.

## 3.2 Social connection

| Method and path | Status | Required V1 contract |
|---|---|---|
| `GET /social/accounts` | **Partial** | List connection/health for the five V1 platforms only. Make clear what access is used for and what data Clippit reads. |
| `GET /social/{platform}/login` | **Partial** | Start official platform authentication for a supported V1 platform. Exact OAuth scopes and endpoint strategy are **TBD**. |
| `GET /social/{platform}/callback` | **Partial** | Complete and persist the supported-platform connection. Production app approval and token lifecycle still need live verification. |
| `POST /social/{platform}/refresh` | **Partial** | Supporting token-lifecycle operation. Refresh when officially supported; otherwise mark reconnect required. |
| `POST /social/{platform}/sync-profile` | **Supporting** | Refresh connected identity/handle and connection health. |
| `DELETE /social/{platform}` | **Compliant** | Disconnect an owned account without changing historical submission/view provenance. |

Connection is not required at account creation. It becomes mandatory only before a Creator submits on that platform.

## 3.3 Creator KYC and bank destination

| Method and path | Status | Required V1 contract |
|---|---|---|
| `GET /creators/me/verification` | **Missing** | Return Creator KYC state and customer-safe next action. Creator may earn before KYC; only bank withdrawal is blocked. |
| `POST /creators/me/verification/session` | **Missing / provider TBD** | Create or resume the selected provider's verification flow. Provider and exact fields remain **TBD**. |
| `POST /webhooks/identity` | **Missing / provider TBD** | Apply verified provider events idempotently once a provider is selected. |
| `GET /admin/creators/verifications` | **Missing** | Operator queue for Creator KYC states and requests. |
| `GET /admin/creators/verifications/{application_id}` | **Missing** | Operator detail with minimally necessary identity/provider evidence and audit history. |
| `POST /admin/creators/verifications/{application_id}/approve` | **Missing** | Audited manual decision only if permitted by the selected provider/policy. |
| `POST /admin/creators/verifications/{application_id}/reject` | **Missing** | Audited rejection/needs-action decision with customer-safe reason. |
| `GET /creators/me/bank-details`, `PUT /creators/me/bank-details` | **Compliant** | Store and return one masked Creator bank destination. The data model must continue to enforce one account per Creator. |
| `POST /creators/me/bank-details/verify` | **Partial** | Resolve/verify the bank destination. Bank resolution is not KYC and must not mark identity as verified. |
| `DELETE /creators/me/bank-details` | **Supporting** | Safely remove the current destination when no transfer is in flight. |

## 3.4 Brand type, KYB, and individual verification

| Method and path | Status | Required V1 contract |
|---|---|---|
| `GET /organisations/me/profile` | **Partial** | Return Individual/Company classification, verification state, and public workspace identity. Current profile has no Brand subtype. |
| `PUT /organisations/me/profile` | **Partial** | Update allowed identity fields without allowing the Brand to self-approve verification. |
| `GET /organisations/me/verification` | **Missing** | Return the applicable Individual verification or Company KYB state and required next action. |
| `POST /organisations/me/verification/session` | **Missing / provider TBD** | Start/resume the applicable verification flow. Provider and exact fields remain **TBD**. |
| `POST /webhooks/business-verification` | **Missing / provider TBD** | Apply provider events idempotently once the provider is selected. |
| `GET /admin/organisations/verifications` | **Missing** | Queue Individual Brand verification and Company KYB applications. |
| `GET /admin/organisations/verifications/{application_id}` | **Missing** | Secure operator detail, checks, history, and minimally necessary documents. |
| `POST /admin/organisations/verifications/{application_id}/approve` | **Missing** | Audited approval. |
| `POST /admin/organisations/verifications/{application_id}/reject` | **Missing** | Audited rejection/needs-action decision. |

Company Brands must not complete required funding/publishing actions until KYB is satisfied. Individual Brands must have the corresponding verification path before money-moving actions that require it. The exact verification provider and provider fields are **TBD**.

## 3.5 Company team and permission checks

| Method and path | Status | Required V1 contract |
|---|---|---|
| `GET /organisations/me/team` | **Missing** | List Company teammates, status, invitation state, and effective capabilities without inventing role names. |
| `POST /organisations/me/team/invitations` | **Missing** | Invite a teammate to a Company Brand with an allowed permission set. |
| `POST /organisations/team-invitations/{token}/accept` | **Missing** | Accept one valid invitation into the Company workspace. |
| `PATCH /organisations/me/team/{member_id}` | **Missing** | Change stored capabilities subject to separation-of-duty and last-owner safeguards. |
| `DELETE /organisations/me/team/{member_id}` | **Missing** | Remove/revoke a teammate without deleting their audit history. |
| `GET /organisations/me/permissions` | **Missing** | Return the caller's effective Company capabilities for UI and API enforcement. |

Exact Company role names and the final permission matrix are **TBD**. The implementation must not hard-code an invented hierarchy; sensitive routes must check capabilities for funding, withdrawals, cancellation, Qwen overrides, team management, and campaign editing.

---

# 4. Wallets, fees, funding, refunds, and withdrawals

## 4.1 Shared wallet and ledger reads

| Method and path | Status | Required V1 contract |
|---|---|---|
| `GET /wallet` | **Partial** | Creator: held, available, withdrawal pending/processing, paid history. Brand: available, campaign-reserved, pending refund/settlement, withdrawal history. Current Brand response omits pending refund/settlement and is not a complete wallet ledger projection. |
| `GET /wallet/ledger` | **Missing** | Role-scoped immutable ledger entries with gross, Clippit fee, net, type, state, and related campaign/submission/withdrawal/refund. |
| `GET /wallet/ledger/{entry_id}` | **Missing** | One owned immutable money event with provenance. |

## 4.2 Initial campaign funding

| Method and path | Status | Required V1 contract |
|---|---|---|
| `POST /campaigns/{campaign_ref}/funding/quote` | **Partial** | Return creator pot, 15% Clippit fee, total allocation cost, currency, and locked terms/confirmation version. Existing quote calculates the fee but is not tied to an explicit immutable-rules/rate confirmation. |
| `POST /campaigns/{campaign_ref}/funding` | **Partial** | Require explicit confirmation that rules/rate lock after launch, reserve/deduct the total through the Brand wallet/Paystack-backed ledger, and create the funding operation idempotently. Existing flow creates a direct provider collection rather than a complete Brand-wallet reservation. |
| `GET /campaigns/{campaign_ref}/funding` | **Partial** | Return funding operation, wallet/ledger effect, Paystack state, and publish prerequisites. |
| `POST /campaigns/{campaign_ref}/funding/confirm` | **Partial** | Confirm authoritative payment/ledger state; go live only after funds and all publish prerequisites, including KYB where required, are satisfied. Current flow does not enforce KYB. |
| `DELETE /campaigns/{campaign_ref}/funding` | **Supporting** | Cancel only an unpaid/unconfirmed operation and release any safe reservation. |
| `POST /webhooks/payments` | **Partial** | Verify the Paystack signature, store a unique provider event/payment record, apply idempotently, and preserve an auditable outcome. Signature handling exists; durable event-envelope deduplication does not. |

## 4.3 Campaign top-up

| Method and path | Status | Required V1 contract |
|---|---|---|
| `POST /campaigns/{campaign_ref}/top-ups/quote` | **Missing** | Quote amount added, 2.5% fee, total wallet/Paystack cost, currency, and immutable campaign rate/rules. |
| `POST /campaigns/{campaign_ref}/top-ups` | **Missing** | Add money to a live campaign idempotently after permission and financial confirmation. Never mutate rate or content rules. |
| `GET /campaigns/{campaign_ref}/top-ups` | **Missing** | List top-up operations and states for Brand/Admin reconciliation. |
| `GET /campaigns/{campaign_ref}/top-ups/{top_up_id}` | **Missing** | Return one top-up, fee, ledger effects, provider state, and failure reason. |

## 4.4 Campaign end and refund ordering

| Method and path | Status | Required V1 contract |
|---|---|---|
| `POST /campaigns/{campaign_ref}/close` | **Partial** | Distinguish Brand manual end, natural end, depletion, and Admin removal. Settle/preserve valid Creator obligations before refund calculation. Current route closes but does not complete the PRD refund/fee transaction. |
| `POST /campaigns/{campaign_ref}/refunds` | **Non-compliant** | Manual end: refund unused uncommitted balance minus 2.5% to the Brand wallet. Natural end: refund unused balance with no cancellation fee. Current service immediately credits the full unused balance and never applies `CANCELLATION_FEE_RATE`. |
| `GET /campaigns/{campaign_ref}/refunds` | **Partial** | Return gross refundable remainder, cancellation fee if applicable, net Brand-wallet credit, protected Creator obligations, state, and ledger references. |
| Natural-end refund job/domain command | **Missing** | Automatically return unused money after obligations when a date/condition naturally ends the campaign; do not apply the manual-cancellation fee. |

## 4.5 Creator withdrawal

| Method and path | Status | Required V1 contract |
|---|---|---|
| `POST /payouts/quote` | **Partial** | Validate at least NGN 5,000, one saved bank account, passed KYC, gross amount, 7% fee, and 93% net. Current quote does not check KYC. |
| `POST /payouts` | **Partial** | Debit the selected gross amount, charge 7%, send 93%, require passed KYC and one verified bank account, and expose requested/processing/succeeded/failed. Current route checks email and bank resolution but has no KYC gate. |
| `GET /payouts` | **Compliant** | Creator withdrawal history. |
| `GET /payouts/{payout_id}` | **Compliant** | Owned withdrawal state, destination snapshot, fee/net, and earning provenance. |

## 4.6 Brand withdrawal

| Method and path | Status | Required V1 contract |
|---|---|---|
| `GET /organisations/me/bank-details`, `PUT /organisations/me/bank-details` | **Compliant** | Store one masked Brand bank destination. |
| `POST /organisations/me/bank-details/verify` | **Partial** | Resolve/verify the destination without substituting for Individual verification or Company KYB. |
| `POST /wallet/withdraw/quote` | **Partial** | Validate available, non-reserved Brand balance, verification/permissions, NGN 5,000 minimum, 7% fee, and 93% net. Current quote does not enforce Brand verification or Company capabilities. |
| `POST /wallet/withdraw` | **Partial** | Debit gross, charge 7%, send 93% to saved verified bank, and enforce verification and Company permissions. |
| `GET /wallet/withdrawals` | **Compliant** | Brand withdrawal history. |
| `GET /wallet/withdrawals/{withdrawal_id}` | **Compliant** | Owned/Admin-visible Brand withdrawal detail. |

## 4.7 Brand transaction views

| Method and path | Status | Required V1 contract |
|---|---|---|
| `GET /organisations/me/transactions` | **Partial** | Unified Brand ledger view across wallet funding/reservations, campaign funding, 15% fees, top-ups/2.5% fees, Creator commitments, refunds/cancellation fees, withdrawals/7% fees, failures, and adjustments. Current view covers only part of this surface. |
| `GET /organisations/me/transactions/{transaction_id}` | **Partial** | One authorized immutable ledger item with full provenance. |
| `GET /organisations/me/transactions/export` | **Supporting** | Safe export of the same ledger truth. |

---

# 5. Campaign creation, discovery, analytics, and lifecycle

## 5.1 Campaign builder and drafts

| Method and path | Status | Required V1 contract |
|---|---|---|
| `POST /campaign-drafts` | **Compliant** | Create an owned resumable draft. |
| `GET /campaign-drafts` | **Compliant** | List the Brand's drafts. |
| `GET /campaign-drafts/{draft_id}` | **Compliant** | Return the owned canonical draft and revision. |
| `PATCH /campaign-drafts/{draft_id}` | **Partial** | Autosave campaign identity, assets, five-platform selection, niche/filter data, public/invite access, pot, rate, minimum, caps, max submissions, rules, and end condition. Niche/filter catalogue remains **TBD**; asset ownership/lifecycle is incomplete. |
| `DELETE /campaign-drafts/{draft_id}` | **Compliant** | Delete an incomplete owned draft. |
| `POST /campaign-drafts/{draft_id}/finalize` | **Partial** | Validate all V1 fields and return the immutable launch preview. Funding/publishing must separately record explicit Brand confirmation that rate and content rules cannot change after launch. |

## 5.2 Campaign fields and invariants

| Field/behavior | Status | Required V1 contract |
|---|---|---|
| Campaign identity | **Compliant** | Title, description/purpose, and Brand-facing metadata. |
| Campaign assets | **Partial** | Brand can upload owned assets Creators should use/reference; Creator detail receives safe asset access. Current campaign schema stores simple name/URL objects without a complete owned upload lifecycle. |
| Platforms | **Partial** | Any subset of the five V1 platforms only. Generic enum/provider code still includes Threads and must not expose it as V1. |
| Niche/Creator filters | **TBD / Partial** | Brand can define niche/filters, but exact catalogue is **TBD**. Store only approved/versioned filters once decided. |
| Access mode | **Compliant** | Public or invite-code. |
| Creator pot and rate | **Compliant before launch** | Pot and rate per 1,000 eligible verified views. Rate becomes immutable after launch. |
| Minimum to earn | **Non-compliant validation** | Must be at least 1,000. Current schema accepts values below 1,000. |
| Per-video and per-Creator caps | **Compliant** | Campaign-configurable and enforced by earnings allocation. |
| Maximum submissions per Creator | **Compliant** | Brand-configurable and enforced. |
| Content rules | **Compliant before launch** | Ordered must/must-not checklist; immutable after launch. |
| End condition | **Partial** | Optional date, pot exhaustion, or configured combination; end date is not mandatory. Current model records only `duration` or `budget` as a primary label and needs an unambiguous API representation. |
| Explicit immutable-terms confirmation | **Missing** | API must persist Brand confirmation of the warning that content rules and payout rate cannot change after launch. |

No separate campaign-asset endpoints are mandatory if the draft/campaign endpoints provide secure owned upload attachment, ordering, replacement, and safe Creator access. The current URL-only asset objects do not yet satisfy that contract.

## 5.3 Campaign CRUD, feed, and participation

| Method and path | Status | Required V1 contract |
|---|---|---|
| `POST /campaigns` | **Partial** | Create the canonical pre-funding campaign with every V1 field and server-side invariant. Existing route remains as a legacy/direct create path and lacks the full confirmation/verification contract. |
| `GET /campaigns` | **Partial** | Creator: discover public live campaigns with prominent rate/remaining pot and supported filters. Brand: portfolio including draft, funding-pending, live, both pause modes, naturally ended, depleted, cancelled, and Admin-removed. Current state model collapses several states. |
| `GET /campaigns/{campaign_ref}` | **Partial** | Before join/submit show immutable rate, remaining pot, five-platform set, minimum, caps, max submissions, end condition, assets, complete rules, access mode, and pause behavior. Most fields exist; lifecycle state and secure asset delivery are incomplete. |
| `PATCH /campaigns/{campaign_ref}` | **Partial** | Allow lifecycle-permitted mutable fields only. Reject any post-launch rule or rate change. Existing route enforces draft-only edits, which is safe but narrower than the PRD's allowed non-rule/rate post-launch edits. |
| `GET /campaigns/{campaign_ref}/rules`, `PUT /campaigns/{campaign_ref}/rules` | **Compliant** | Read rules; replace only before launch. |
| `PUT /campaigns/{campaign_ref}/payout-rule` | **Partial** | Replace only before launch; enforce minimum threshold >= 1,000 plus per-video/per-Creator caps and max submissions. |
| `POST /campaigns/{campaign_ref}/join` | **Compliant** | Join live/public or valid invite-code campaign after supported-platform connection/capability checks. |
| `DELETE /campaigns/{campaign_ref}/join` | **Compliant** | Leave before participation has created protected history/earnings. |
| `GET /creators/me/campaigns` | **Compliant** | Creator participation history/status. |

## 5.4 Pause, resume, end, and state

| Method and path | Status | Required V1 contract |
|---|---|---|
| `POST /campaigns/{campaign_ref}/pause?mode=acquisition` | **Compliant** | Stop new joins/submissions while already-approved content continues earning. |
| `POST /campaigns/{campaign_ref}/pause?mode=full` | **Compliant** | Stop new activity and freeze new campaign earnings until resume. |
| `POST /campaigns/{campaign_ref}/resume` | **Compliant** | Restore live behavior subject to remaining pot and end conditions. |
| `POST /campaigns/{campaign_ref}/close` | **Partial** | Record manual, natural, depleted, or Admin-removed outcome and invoke the correct fee/refund behavior. |
| Campaign state in list/detail responses | **Partial** | Expose Draft, Funding/publish pending, Live, Paused-acquisition, Paused-full, Ended-natural, Depleted, Cancelled/manual, and Admin-removed. Current API primarily exposes draft/pending/active/closed plus secondary flags/reason. |

## 5.5 Brand dashboard and analytics

| Method and path | Status | Required V1 contract |
|---|---|---|
| `GET /brand/overview` | **Partial** | Wallet summary plus active, paused, completed, cancelled, and draft portfolio signals. Current overview does not represent every V1 lifecycle/wallet state. |
| `GET /campaigns/{campaign_ref}/stats` | **Partial** | Current total verified views, spend, remaining pot, submissions, approvals/reviews, Creator performance, and end-condition status. Existing stats are narrower. |
| `GET /campaigns/{campaign_ref}/analytics` | **Missing** | Official verified-view growth; spend/pot; Creator earnings committed/held/available; effective cost per 1,000; submission counts by AI/human/override/appeal state; per-Creator/per-video performance; top performers. |
| `GET /campaigns/{campaign_ref}/submissions` | **Partial** | Brand submission list with V1 verdict/review/appeal and performance states. |
| `GET /campaigns/{campaign_ref}/report` | **Supporting** | CSV export may remain, but it is not a substitute for the required analytics response. |

---

# 6. Submission, Qwen compliance, Brand review, and appeals

## 6.1 Creator submission contract

| Method and path | Status | Required V1 contract |
|---|---|---|
| `POST /submissions` | **Partial** | Accept campaign, supported platform, and live post URL only; require the matching connected account; validate context/ownership; retrieve with yt-dlp; start Qwen analysis. Current body still permits an optional manual `video_upload_id`, and Qwen is not the required production default. |
| `GET /submissions` | **Partial** | Role-scoped list with the complete V1 state model. |
| `GET /submissions/{submission_id}` | **Partial** | Return URL validation, retrieval, Qwen/human state, rule breakdown, evidence/timestamps, confidence, model/version, five-day deadline, appeal, fraud hold, and earning state. Current response lacks several durable fields/states. |
| `POST /submissions/{submission_id}/withdraw` | **Supporting** | Stop future participation/tracking without deleting history or recognized earnings. |
| `POST /submissions/{submission_id}/resubmit` | **Partial / policy TBD** | Correction chain exists. Duplicate URL/resubmission policy is **TBD** and must not be silently hard-coded beyond the Brand's max-submission rule. |

The campaign-submission product must not ask the Creator to upload a second video. Generic uploads may remain for profile photos, campaign assets, KYC/KYB, or appeal evidence, but not as a required submission step.

## 6.2 Qwen compliance behavior

| Required behavior | Status | Current gap |
|---|---|---|
| yt-dlp retrieves posted video from URL | **Partial** | Implemented, but must be operated as the normal V1 path and verified for all five supported platforms. |
| Qwen3.8-Omni-Flash receives native video including audio | **Partial** | Adapter exists; production is disabled by default and not live-proven. |
| Overall `APPROVED`, `REJECTED`, or `HUMAN_REVIEW_REQUIRED` | **Compliant in adapter** | Persist as explicit product state, including technical failure separately. |
| One pass/fail/uncertain result per immutable campaign rule | **Compliant in adapter** | Ensure missing model rows demote to human review and remain stored. |
| Evidence and timestamps where possible | **Partial** | Currently combined into free-text notes instead of durable structured evidence/timestamp fields. |
| Machine-readable confidence | **Compliant** | Stored as submission confidence; rule-level confidence is not currently retained. |
| Human-review reason | **Partial** | Summary exists, but needs a distinct durable reason/code. |
| Model/version metadata | **Partial** | Model is embedded into summary text rather than stored as a dedicated immutable field/version record. |
| Technical failure/retry state | **Partial** | Correctly avoids auto-rejection, but currently collapses failure into `needs_review` rather than exposing retrieval/model failure and retry state. |
| Automation is default | **Non-compliant configuration** | Default verifier is manual review. V1 requires Qwen to reduce Brand workload; AI-approved submissions must not require mandatory manual approval. |

The PRD does not require a separate internal verification HTTP API if the monolith executes the same durable workflow. Queue/callback endpoints are an implementation choice, not a V1 product requirement.

## 6.3 Brand/Admin authority and review actions

| Method and path | Status | Required V1 contract |
|---|---|---|
| `GET /brand/reviews` | **Partial** | Include Qwen-approved submissions still inside the five-day review window, uncertain cases, rejections/appeals, deadlines, and reminder state. |
| `GET /brand/reviews/{submission_id}` | **Partial** | Show immutable rules, Qwen evidence/timestamps/model, five-day deadline, held exposure, prior overrides, and appeal context. |
| `POST /brand/reviews/{submission_id}/approve` | **Partial** | Brand can approve human-review/appeal cases and override an AI rejection with reason/audit. Current transition coverage is narrower. |
| `POST /brand/reviews/{submission_id}/request-correction` | **Non-compliant transition** | Brand must be able to reject an AI-approved submission inside the five-day window and provide a reason. Current service refuses decisions on already-approved submissions. |
| Admin override through submission review actions | **Partial** | Admin may use current review routes, but every AI approval/rejection must be overrideable within authority and record prior/new verdict, actor, reason, and timestamp. Current audit payload is incomplete. |
| `POST /submissions/{submission_id}/appeal` | **Partial** | Support AI rejection, Brand/human rejection, and fraud-enforcement appeal where applicable. Current route only accepts content-verification rejection. |

## 6.4 Five-day submission review window

| Required behavior | Status | Current gap |
|---|---|---|
| Qwen approval starts one five-day window | **Missing as a first-class state** | No durable `review_window_ends_at` tied to Qwen approval. |
| Views and provisional earnings accrue during the window | **Partial** | Views/earnings accrue, but the hold is modeled per earning entry. |
| In-window Brand rejection blocks unrecognized held earnings | **Missing** | Approved submissions cannot currently be rejected through the Brand action. |
| Window expiry recognizes held money automatically | **Partial** | Each accrual gets its own five-day `payable_at`, producing a rolling hold rather than one submission review deadline. |
| Late Brand rejection stops future earnings only | **Missing** | No explicit late-rejection transition preserving already recognized earnings. |
| Brand reminder before expiry | **Missing / notification provider TBD** | Required event is not fully implemented. |

---

# 7. Official views, earnings, fraud, and leaderboards

## 7.1 Official view ingestion

| Method and path | Status | Required V1 contract |
|---|---|---|
| `POST /internal/submissions/{submission_id}/metrics` | **Partial** | Register/poll a submission using official APIs only and store timestamped readings. Instagram, TikTok, Facebook, and YouTube adapters target official sources; X currently uses `twitterapi.io`, which violates the locked official-API-only rule. |
| `GET /internal/submissions/{submission_id}/performance` | **Compliant structurally** | Read stored official snapshots/provenance without accepting human-entered views. Becomes V1-compliant only when every platform source is official. |
| `GET /submissions/{submission_id}/performance` | **Compliant structurally** | Authorized customer-safe performance view over stored readings. |
| Polling worker/domain job | **Partial / cadence TBD** | Scheduling and retention exist. Exact cadence per platform is **TBD**; provider limits/permissions must be respected. |

X payable metrics must move from `twitterapi.io` to an official X API source or X must remain disabled for payable V1 campaigns until an official source is available. The PRD does not permit a third-party substitute.

## 7.2 Earnings and pot allocation

| Method and path | Status | Required V1 contract |
|---|---|---|
| Earnings settlement domain job | **Partial** | Enforces whole thousands, pot ceiling, and caps, but must adopt the submission-level five-day review window and complete wallet-ledger provenance. |
| `GET /earnings/summary` | **Partial** | Return held, available, withdrawal pending/processing, and paid balances under the corrected review-window rules. |
| `GET /earnings/history` | **Partial** | Immutable earning events with view basis, complete-thousand increment, rate, cap effects, pot before/after, review deadline, and wallet state. Current response is narrower. |
| `GET /earnings/entries/{entry_id}` | **Partial** | One owned earning event with complete official-reading and ledger provenance. |
| `GET /submissions/{submission_id}/earnings` | **Partial** | Submission earnings exposure with held/recognized/available states and the one review deadline. |

## 7.3 Fraud review and appeal

| Method and path | Status | Required V1 contract |
|---|---|---|
| `GET /admin/submissions/flagged` | **Partial** | Fraud queue with affected earnings, evidence/signals, state, and appeal. Fraud thresholds/algorithm remain **TBD**. |
| `GET /admin/submissions/{submission_id}` | **Partial** | Full official readings, signals, earnings exposure, Qwen/Brand decisions, appeals, and audit history. |
| `POST /admin/submissions/{submission_id}/trust/confirm` | **Partial** | Freeze affected earnings and record an auditable fraud enforcement decision without inventing thresholds. |
| `POST /admin/submissions/{submission_id}/trust/clear` | **Partial** | Clear the fraud hold and resume eligible behavior. |
| `POST /submissions/{submission_id}/appeal` | **Partial** | Must also accept an appeal of fraud enforcement where applicable. |

Post-payout fraud recovery policy is **TBD**. Do not claw back or create debt automatically without an approved policy.

## 7.4 Leaderboards

| Method and path | Status | Required V1 contract |
|---|---|---|
| `GET /leaderboard` | **Partial** | Support `scope` values `global`, `country`, and `campaign`, plus `rank_by` values `verified_views` and `earnings`, using only official views and valid Clippit earnings. Current endpoint supports global/country plus campaign filter but ranks only by verified views. |

Country context must be configured/verified. No state/city ranking belongs in V1.

---

# 8. Notifications

V1 requires in-app, push, and email channels for major product events. Provider choice, templates, and delivery retry policy are **TBD**; the underlying event catalogue and delivery records are not TBD.

## 8.1 Customer notification API

| Method and path | Status | Required V1 contract |
|---|---|---|
| `GET /notifications` | **Partial** | Inbox for every required Creator/Brand event with channel/delivery state where customer-safe. Event coverage is incomplete. |
| `GET /notifications/unread-count` | **Compliant** | Cheap unread badge count. |
| `POST /notifications/{notification_id}/read` | **Compliant** | Mark one owned notification read. |
| `POST /notifications/read-all` | **Compliant** | Mark all owned notifications read. |
| `POST /notifications/{notification_id}/archive` | **Supporting** | Archive one owned notification. |
| `POST /push-subscriptions` | **Partial** | Store an owned push subscription. Actual push delivery/provider integration is not implemented. |
| `DELETE /push-subscriptions/{subscription_id}` | **Compliant structurally** | Remove an owned subscription. |
| `GET /profile/preferences`, `PATCH /profile/preferences` | **Partial** | Channel/event preferences may vary, but required product events must still be emitted under the approved policy. |

## 8.2 Required event catalogue

Creator events:

- submission received;
- Qwen approved, rejected, or human review required;
- appeal update;
- campaign paused, resumed, ended, cancelled, or depleted;
- earnings held and unlocked;
- KYC state change;
- withdrawal requested, succeeded, or failed;
- fraud/review action.

Brand events:

- campaign funded/live;
- low or empty pot;
- new submission;
- Qwen human-review required;
- five-day review reminder;
- appeal update;
- top-up result;
- pause/resume;
- natural end/manual cancel/refund;
- KYB state change;
- Brand-wallet withdrawal state.

Company teammate events are filtered by effective permission. Admin receives review queues, escalations, fraud flags, failed money movement, enforcement alerts, and operational exceptions.

## 8.3 Delivery operations

| Method and path | Status | Required V1 contract |
|---|---|---|
| `GET /admin/notifications` | **Missing** | Inspect required notification events and delivery states across in-app, email, and push. |
| `GET /admin/notifications/{notification_id}` | **Missing** | Redacted event, recipient/channel, attempts, timestamps, and outcome. |

An Admin retry command is not required until the TBD delivery retry policy is approved.

---

# 9. Admin application

Admin has platform-wide visibility and enforcement authority. Brand remains final authority over whether content satisfies that Brand's campaign rules.

| Method and path | Status | Required V1 contract |
|---|---|---|
| `GET /admin/overview` | **Partial** | Platform review queues, escalations, fraud, money failures, campaign/account state, and operational exceptions. |
| `GET /admin/users` | **Partial** | All Creator/Brand accounts, account type/subtype, verification states, restrictions, and relevant activity. |
| `GET /admin/users/{user_id}` | **Partial** | Safe account, KYC/KYB, social health, wallet summary, campaigns/submissions, restrictions, and audit history. |
| `POST /admin/users/{user_id}/suspend` | **Compliant structurally** | Audited account restriction with scope/reason. |
| `POST /admin/users/{user_id}/restore` | **Compliant structurally** | Audited restoration. |
| Creator KYC queue/detail/decision routes | **Missing** | See section 3.3. |
| Brand verification/KYB queue/detail/decision routes | **Missing** | See section 3.4. |
| `GET /admin/campaigns` | **Partial** | All campaigns including operationally permitted drafts, every V1 lifecycle state, pots, fees, top-ups, and refunds. |
| `GET /admin/campaigns/{campaign_ref}` | **Partial** | Terms, immutable fields, funding/wallet ledger, submissions, performance, pause history, refund state, and audit. |
| `POST /admin/campaigns/{campaign_ref}/pause` | **Partial** | Enforcement pause with explicit behavior and audit. |
| `POST /admin/campaigns/{campaign_ref}/remove` | **Missing** | Remove a violating campaign into the distinct Admin-removed state; preserve money/submission/audit history and apply approved settlement/refund behavior. |
| `GET /admin/submissions` | **Partial** | Global Qwen/human/fraud/appeal queue and search. |
| `GET /admin/submissions/{submission_id}` | **Partial** | Qwen verdict/evidence/model, override history, official views, fraud, appeals, and earnings exposure. |
| Admin Qwen override action | **Partial** | Existing review actions are transition-limited and do not store the complete prior/new verdict audit required by V1. |
| Fraud queue/detail/clear/confirm routes | **Partial** | See section 7.3. |
| `GET /admin/ledger` | **Partial** | Unified immutable wallet/campaign/fee/top-up/earning/refund/withdrawal ledger. Current ledger omits parts of the V1 wallet model. |
| `GET /admin/ledger/{entry_id}` | **Partial** | One fully reconstructable money event. |
| `GET /admin/payouts` and payout actions | **Partial** | Inspect Creator transfers, failures, and reconciliation. Must include KYC state and immutable ledger linkage. |
| `GET /admin/refunds` | **Partial** | Inspect natural/manual refund ordering, gross, fee, net, protected obligations, and failure state. |
| `GET /admin/funding` | **Partial** | Inspect Brand-wallet reservation, 15% fee, Paystack collection, and campaign go-live state. |
| `GET /admin/providers` | **Partial** | Operational state for Paystack, Qwen/yt-dlp, five official social APIs, KYC/KYB provider when selected, email, and push. Current provider response is narrower and still describes non-compliant X sourcing. |
| `GET /admin/webhooks` | **Missing** | Inspect stored/redacted payment and verification events and handler outcomes. |
| `GET /admin/webhooks/{event_id}` | **Missing** | One stored event with signature result, attempts, linked resource, and result. |
| `GET /admin/audit` | **Partial** | Search sensitive Admin/Brand overrides, enforcement, compliance decisions, and money activity. Current audit records do not uniformly hold prior/new state and correlation/provenance. |
| `GET /admin/audit/{event_id}` | **Partial** | One complete audit event. |

Support tickets, generic disputes, abuse reports, legal-document management, public profiles, official PDF receipts, invoices, and account export may be valuable broader-product features, but they are not stated V1 acceptance requirements in this PRD and are not counted as PRD blockers here.

---

# 10. Required state models

## 10.1 Campaign states

API responses must expose these customer-meaningful states even if persistence uses a base state plus reason/mode fields.

| State | Required meaning | Current status |
|---|---|---|
| Draft | Being configured; not visible or earning | Built |
| Funding/publish pending | Waiting on finance/verification/publish prerequisites | Partial; KYB and explicit terms confirmation absent |
| Live | Eligible participation; approved submissions can earn | Built |
| Paused - acquisition only | No new joins/submissions; approved content keeps earning | Built via flags/mode |
| Paused - full freeze | No new activity and no new earnings until resume | Built via flags/mode |
| Ended - natural | Configured end condition completed | Partial; refund behavior incomplete |
| Depleted | Pot reached zero; all future earning stops | Partial; represented as closed reason, not a full customer state |
| Cancelled/manual | Brand ended early; 2.5% refund fee applies | Partial; fee/refund transaction incorrect |
| Admin removed | Enforcement removal | Missing distinct state/action |

## 10.2 Submission states

| State | Can earn? | Can withdraw? | Current status |
|---|---:|---:|---|
| Submitted/processing | No | No | Built, but retrieval/Qwen sub-states need explicit fields |
| Retrieval/model technical failure | No | No | Partial; collapsed into human review |
| AI rejected | No | No | Built |
| Human review required | No | No | Built |
| Approved - five-day hold | Provisional/held only | No | Missing as a first-class submission-level window |
| Approved - active | Yes, subject to rules/pot/caps | Available balance only after KYC for bank withdrawal | Partial |
| Rejected after hold window | Future earnings stop | Recognized balance remains | Missing explicit transition |
| Fraud review | Affected earning frozen | Affected amount unavailable | Partial |
| Appeal/final resolution | Follows final authority decision | Follows recognized/held state | Partial |

---

# 11. Minimum data to retain

| Record | Required minimum |
|---|---|
| Campaign | Owner, Brand subtype/workspace, access mode, immutable rules, immutable rate, pot, all Clippit fees, caps, max submissions, end condition, pause history, assets, mutable edit history, explicit launch confirmation |
| Submission | Creator, campaign, platform, URL, retrieval/technical state, retained media reference/policy, Qwen model/version, structured verdict, per-rule evidence/timestamps/confidence, five-day deadline, appeals, overrides |
| View reading | Official platform/source, post/submission, reading, timestamp, raw/reference metadata needed for reconciliation |
| Earning event | Source reading, eligible complete-thousand increment, immutable rate, cap checks, pot before/after, submission review window, held/recognized/available state |
| Wallet ledger | Account, debit/credit type, gross, Clippit fee, net, related campaign/submission/funding/top-up/withdrawal/refund, state, timestamps, provider references |
| Brand/Admin override | Actor, authority/scope, prior state, new state, reason, timestamp |
| Notification | Event type, recipient, channel, delivery state, attempts/timestamps allowed by the approved TBD policy |

Current storage is **Partial** against this table. Notable gaps include Brand subtype/team permissions, KYC/KYB, top-up ledger records, correct refund fees, explicit review deadlines, structured Qwen model/evidence metadata, complete wallet ledger coverage, and complete override audit payloads.

---

# 12. External integrations

| Integration | Locked purpose | Current status |
|---|---|---|
| Paystack | Collection, bank/payout rails, and wallet-related money movement | Adapter built and fixture-tested; live end-to-end movement/reconciliation still unproven |
| yt-dlp | Retrieve creator-posted media from the submitted URL | Built; must be the normal URL-only submission path |
| Qwen3.8-Omni-Flash / Alibaba Cloud Model Studio | Native video+audio rule evaluation | Built behind configuration; default remains manual and production path is unproven |
| Instagram official API | Official payable view data | Built/fixture-tested; production permissions TBD |
| TikTok official API | Official payable view data | Built/fixture-tested; production permissions TBD |
| Facebook official API | Official payable view data | Built/fixture-tested; production permissions TBD |
| X official API | Official payable view data | **Non-compliant**: current metrics use `twitterapi.io`, not an official X source |
| YouTube official API | Official payable view data | Built/fixture-tested; live credentials/quota verification pending |
| KYC/KYB provider | Verification before required money movement/publishing | **TBD and not implemented** |
| Email/push provider | Major-event delivery | **TBD**; in-app records and subscription storage exist, full delivery does not |

Cloudflare R2, Deepgram, FFmpeg, Inngest, Celery, Redis, Sentry, a particular KYC vendor, and a particular push/email vendor are not locked V1 product choices in this PRD. They may be selected as implementation architecture, but this inventory must not describe them as product-mandated endpoints or providers.

---

# 13. PRD acceptance checklist

| Acceptance requirement | Current result |
|---|---|
| Creator submits a supported social URL without manually uploading the video | **Partial** - URL works, but API still accepts an optional video upload and the frontend/path must be URL-only |
| Every Qwen verdict has rule-by-rule output; uncertainty enters human review | **Partial** - adapter supports it; structured persistence is incomplete and Qwen is not the default |
| AI approval does not require mandatory Brand approval before the five-day hold | **Fail** - default verifier is manual, and review-window semantics are not implemented correctly |
| Brand receives reminders; late rejection cannot remove recognized earnings | **Fail** - reminder and late-rejection transition are missing |
| 100% of payable views originate from official APIs | **Fail** - X uses `twitterapi.io` |
| Campaign balance cannot become negative or pay more than funded pot | **Pass in core settlement tests/design** |
| Fees are 15% initial, 2.5% top-up, 2.5% manual-cancel remainder, 7% wallet withdrawal | **Fail** - top-up is missing and cancellation rate is unused |
| Unused money returns to Brand wallet after Creator obligations | **Partial** - basic refund exists; fee ordering and natural-end automation are wrong/missing |
| Creator may earn before KYC but cannot bank-withdraw until KYC passes | **Fail** - no KYC model/gate |
| Company Brand cannot fund/publish before KYB | **Fail** - no Company subtype/KYB gate |
| Brand chooses acquisition-only pause or full earning freeze | **Pass** |
| Global, Country, and Campaign leaderboards rank by views and earnings | **Fail** - views only |
| Sensitive overrides, money movement, and compliance decisions are reconstructable | **Partial** - broad audit exists, but required provenance is incomplete |

The backend is not V1-complete until every **Fail**, **Missing**, and product-material **Partial** row above is resolved or an explicit PRD amendment changes the requirement.

---

# 14. Open implementation decisions - preserve as TBD

These are the complete TBD items named by the V1 PRD. Do not silently decide them in code or documentation.

| TBD item | Locked boundary around the decision |
|---|---|
| Company team role names and exact permission matrix | Company teams and permission checks for sensitive actions are required; only names/matrix remain open |
| KYC/KYB vendor and exact verification fields | Creator payout KYC, Company KYB before funding/publishing, and the Individual verification path are required |
| Exact social OAuth scopes and official API endpoint strategy | The five official platforms and official payable-view sources are fixed |
| View polling cadence by platform | Readings must be official, timestamped, retained, and respect platform limits |
| Fraud thresholds/detection algorithm | Fraud review, earning freeze, Admin decision, and appeal behavior are required |
| Duplicate URL/resubmission policy | Brand-configured maximum submissions is fixed; duplicate handling remains open |
| Notification provider, templates, and delivery retry policy | In-app, email, and push channels plus the event catalogue are fixed |
| Post-payout fraud recovery policy | Fraud review exists, but automatic recovery after money leaves Clippit is not authorized |
| Campaign niche/Creator filter catalogue | Brand filtering is required; exact catalogue is not defined |

---

# 15. Explicit V1 exclusions and non-requirements

The following must not be added to the PRD checklist unless the PRD is amended:

- social platforms other than Instagram, TikTok, Facebook, X, and YouTube;
- Threads as a V1 customer platform;
- creator-entered payable views;
- a required manual video upload during campaign submission;
- a state/city leaderboard;
- one-click Creator/Brand role switching;
- invented Company role names or permission hierarchy;
- invented fraud thresholds;
- invented duplicate URL/resubmission policy;
- invented post-payout debt/clawback policy;
- a provider other than Paystack for the locked V1 payment contract;
- Payaza naming in API/UI contracts;
- transcript-only compliance as a replacement for Qwen native video+audio analysis;
- mandatory Brand approval for every Qwen-approved submission;
- changing content rules or payout rate after launch;
- applying the 2.5% cancellation fee to natural completion or pot depletion;
- passing Paystack/system charges through as extra customer fees;
- treating public profiles, help articles, generic support tickets, legal CMS, PDF receipts, invoices, 2FA, email change, privacy export, or a specific infrastructure vendor as V1 PRD acceptance requirements.

Those broader features may remain implemented or planned. They must be tracked in a separate roadmap rather than represented as requirements from this PRD.
