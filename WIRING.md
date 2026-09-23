# Clippit — API Wiring Status

Tick `- [x]` once you've visually confirmed a feature end-to-end.
Auth was tested in a prior session and is pre-checked. Everything else is wired but not yet visually confirmed.

---

## Legend

| Badge | Meaning |
|-------|---------|
| ✅ Tested | Confirmed working in a real session |
| 🟡 Wired | Code connected — not yet visually confirmed |
| 🔵 Partial | Wired but endpoint has a dependency caveat |
| 🔴 Blocked | Endpoint missing or dependency not ready |

---

## Authentication

| # | Feature | Endpoint | Status |
|---|---------|----------|--------|
| - [x] | Creator & brand login | `POST /auth/login` | ✅ Tested |
| - [x] | Creator & brand registration | `POST /auth/register` | ✅ Tested |
| - [x] | Auto token refresh on 401 (client interceptor) | `POST /auth/refresh` | ✅ Tested |
| - [x] | Logout | `POST /auth/logout` | ✅ Tested |

---

## Shell — Badges & Counters

> `ProductShell` (dashboard) + `BrandShell` (brand)

| # | Feature | Endpoint | Status |
|---|---------|----------|--------|
| - [ ] | Dashboard wallet pill — payable balance | `GET /earnings/summary` | 🟡 Wired |
| - [ ] | Dashboard notification bell — unread count | `GET /notifications/unread-count` | 🟡 Wired |
| - [ ] | Brand shell notification bell — unread count | `GET /notifications/unread-count` | 🟡 Wired |
| - [ ] | Brand nav — pending-reviews badge on Review queue link | `GET /brand/overview` | 🟡 Wired |
| - [ ] | Brand topbar — live pot value (`total_pot − total_spent`) | `GET /brand/overview` | 🟡 Wired |

---

## Dashboard Home

> `/dashboard`

| # | Feature | Endpoint | Status |
|---|---------|----------|--------|
| - [ ] | Featured campaign card (closing-soon campaign) | `GET /creators/me/overview` | 🟡 Wired |
| - [ ] | Earnings receipt — total, payable, in-hold, paid all time, active clips | `GET /creators/me/overview` | 🟡 Wired |
| - [ ] | Campaign tape row (up to 6 new campaigns) | `GET /campaigns?feed=all&page_size=6` | 🟡 Wired |
| - [ ] | Mini leaderboard (top 4, weekly) | `GET /earnings/leaderboard?period=week` | 🟡 Wired |

---

## Campaign Directory & Detail

> `/dashboard/campaigns`

| # | Feature | Endpoint | Status |
|---|---------|----------|--------|
| - [ ] | Campaign directory — list with feed filter tabs (All / For you / Closing soon / Joined) | `GET /campaigns?feed={filter}` | 🟡 Wired |
| - [ ] | Campaign detail — brief, rules, payout vitals | `GET /campaigns/{slug}` | 🟡 Wired |
| - [ ] | Campaign detail — sidebar leaderboard (top 3 for this campaign) | `GET /earnings/leaderboard?campaign={slug}` | 🟡 Wired |
| - [ ] | Full leaderboard screen | `GET /earnings/leaderboard?period=week` | 🟡 Wired |

---

## Creator Flows

> `/dashboard/withdraw` · `/dashboard/campaigns/*/submit`

| # | Feature | Endpoint | Status |
|---|---------|----------|--------|
| - [ ] | Withdraw screen — payable balance | `GET /earnings/summary` | 🟡 Wired |
| - [ ] | Withdraw screen — bank account display (name, masked number, verified state) | `GET /creators/me/bank-details` | 🟡 Wired |
| - [ ] | Submit clip — campaign title, brand, rate, platform list | `GET /campaigns/{slug}` | 🟡 Wired |

---

## Payout Account Setup

> `/dashboard/payout-account`

| # | Feature | Endpoint | Status | Notes |
|---|---------|----------|--------|-------|
| - [ ] | Bank selector dropdown | `GET /banks` | 🔵 Partial | Dependency-pending in production — 7-bank hardcoded fallback used as default |
| - [ ] | Account name resolution (fires on 10-digit account number) | `POST /banks/resolve` | 🔵 Partial | Dependency-pending: production bank provider not connected. Fails gracefully — submit is blocked until resolved |
| - [ ] | Save bank details on confirm | `PUT /creators/me/bank-details` | 🟡 Wired | |

---

## Connected Accounts

> `/dashboard/accounts`

| # | Feature | Endpoint | Status |
|---|---------|----------|--------|
| - [ ] | Load platform accounts (handle, connectable status, last-checked time) | `GET /social/accounts` | 🟡 Wired |
| - [ ] | Disconnect a platform | `DELETE /social/{platform}` | 🟡 Wired |

---

## Creator Settings

> `/dashboard/settings`

| # | Feature | Endpoint | Status |
|---|---------|----------|--------|
| - [ ] | Profile — load display name, bio, photo URL | `GET /creators/me/profile` | 🟡 Wired |
| - [ ] | Profile — save changes | `PUT /creators/me/profile` | 🟡 Wired |
| - [ ] | Payout account — display saved bank detail or Add account CTA | `GET /creators/me/bank-details` | 🟡 Wired |
| - [ ] | Notifications — load 4 toggle states | `GET /profile/preferences` | 🟡 Wired |
| - [ ] | Notifications — PATCH on each toggle change | `PATCH /profile/preferences` | 🟡 Wired |

---

## Brand Live Campaign

> `/brand/campaigns/{slug}`

| # | Feature | Endpoint | Status |
|---|---------|----------|--------|
| - [ ] | Campaign header — title, brand name, status | `GET /campaigns/{slug}` | 🟡 Wired |
| - [ ] | Campaign stats — verified views, approvals, review/checking/rejected breakdown | `GET /campaigns/{slug}/stats` | 🟡 Wired |
| - [ ] | Submissions table — creator, platform, verified views, earned, state | `GET /campaigns/{slug}/submissions` | 🟡 Wired |

---

## Brand Review Queue & Detail

> `/brand/reviews`

| # | Feature | Endpoint | Status |
|---|---------|----------|--------|
| - [ ] | Review queue — list + needs-review / appeals / resolved tab counts | `GET /brand/reviews?tab={tab}` | 🟡 Wired |
| - [ ] | Review detail — load creator name, confidence score, flagged issue | `GET /brand/reviews/{id}` | 🟡 Wired |
| - [ ] | Approve submission | `POST /brand/reviews/{id}/approve` | 🟡 Wired |
| - [ ] | Request a correction | `POST /brand/reviews/{id}/correction` | 🟡 Wired |

---

## Brand Settings

> `/brand/settings`

| # | Feature | Endpoint | Status |
|---|---------|----------|--------|
| - [ ] | Organisation identity — load name, bio, website, legal name, verified state | `GET /organisations/me/profile` | 🟡 Wired |
| - [ ] | Organisation identity — save changes | `PATCH /organisations/me/profile` | 🟡 Wired |
| - [ ] | Campaign alerts — load 3 toggle states (funding, reviews, weekly report) | `GET /profile/preferences` | 🟡 Wired |
| - [ ] | Campaign alerts — PATCH on each toggle change | `PATCH /profile/preferences` | 🟡 Wired |

---

## 🔴 Blocked — Not Wirable

These cannot be tested because the endpoint is missing or a dependency is not ready.

| Feature | Endpoint | Reason |
|---------|----------|--------|
| Submit a clip to a campaign | `POST /submissions` | Automated brief verifier not ready (dependency pending) |
| Initiate a withdrawal / payout | `POST /payouts` | Live money rehearsal not ready (dependency pending) |
| Campaign join / leave | `POST\|DELETE /campaigns/{ref}/join` | Missing P0 — endpoints not yet built |
| Brand transaction history | `GET /organisations/me/transactions` | Missing P0 — endpoint not yet built |
| Submit an appeal | `POST /submissions/{id}/appeal` | Static route `/dashboard/submissions/appeal` has no submission ID in the URL |

---

## Summary

| Status | Count |
|--------|-------|
| ✅ Tested | 4 |
| 🟡 Wired (not yet confirmed) | 38 |
| 🔵 Partial (dependency caveat) | 2 |
| 🔴 Blocked | 5 |
| **Total wired** | **44** |
