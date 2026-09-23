# Clippit PRD v1 frontend compliance

Source of truth: `Clippit_Product_Requirements_Document_V1.0.pdf`.

## Customer-language rule

Creator and Brand screens describe outcomes, requirements, statuses, fees and next actions. They do not expose model names, model scores, media-retrieval tooling, internal review thresholds, provider webhooks or implementation details. Operational provider detail is restricted to the internal Admin workspace where it is needed for reconciliation.

## Creator experience

- Registration and role-specific onboarding collect creator profile, preferences, discovery source and an optional profile photo.
- Connected accounts support TikTok, Instagram, Facebook, X and YouTube.
- Campaign discovery and detail show the rate, remaining pot, minimum views, creator cap, per-video cap, maximum submissions, platforms, access mode, content rules, assets and end condition.
- Joining a campaign uses the campaign join endpoint.
- Submission accepts a public social-post URL only. There is no creator video-upload control.
- Submission states cover checking, approval, correction/rejection and human appeal without exposing internal scoring or tooling.
- Approved clips enter the five-day Brand review window while official views are tracked and earnings are held.
- Earnings separate held, available, processing and paid money.
- Creator withdrawals require identity verification, one verified bank account, a ₦5,000 minimum and show the 7% fee before confirmation.
- Leaderboards support Global, Country and Campaign scopes, ranked by views or earnings.

## Brand experience

- Brand onboarding supports individual and registered-company paths, profile details and an optional profile photo.
- The campaign builder covers identity, cover/assets, niche, public/invite access, five platforms, requirements, minimum views, per-video and per-creator caps, maximum submissions, creator pot, rate and date/pot end conditions.
- The review step explicitly confirms that content rules and payout rate lock at launch.
- Initial campaign funding reserves Brand-wallet money and shows the non-refundable 15% campaign fee.
- Live campaign controls support acquisition-only pause, full pause, resume, top-up and campaign end.
- Top-ups show the 2.5% fee and do not change the live rate or content rules.
- Manual cancellation shows the 2.5% charge on the refundable unused balance, preserves recognised creator earnings and returns the net amount to the Brand wallet.
- Review screens show the requirement needing a decision and the five-day review implications without model confidence or hidden thresholds.
- Brand wallet surfaces show available, reserved and pending-refund money. Brand withdrawals show the ₦5,000 minimum and 7% fee.
- Campaign analytics, transaction receipts, closeout, notifications, team, billing and verification remain reachable from Brand navigation.

## Shared and operations

- Customer help and legal content states the 15% campaign fee, 2.5% top-up fee, 2.5% manual-cancellation fee, 7% withdrawal fee and ₦5,000 withdrawal minimum.
- Receipts use Clippit references and customer-readable money destinations rather than exposing internal rails.
- Admin platform health covers all five supported social platforms.
- Admin payment operations use Paystack consistently with the PRD.
- Verification, support, disputes, notifications, consent, account export/deletion and audit surfaces remain present.

## Backend contract follow-up

The frontend accepts the PRD fields `access_mode`, `assets`, `end_condition`, `video_cap`, `max_submissions`, `video_cap_amount` and `max_submissions` when returned by campaign APIs. Until the backend sends them, safe display defaults keep older API responses compatible.
