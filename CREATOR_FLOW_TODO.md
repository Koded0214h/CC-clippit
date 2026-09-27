# Creator flow — status

Last updated 26 Sep 2026, after the backend redeploy.

**All the code is done.** Every creator screen uses the live API, and the last live test found no code bugs.
**Configuration is what's left:** Render env vars, platform developer portals, and one real run with money.

**Legend:** 🔴 blocks the creator flow · 🟠 needed before real users/money · 🟡 product decision or polish

---

## Where we are

| Area | Status |
|---|---|
| Frontend wiring (all creator screens) | ✅ Done: pushed in `b7f855d` |
| Backend fixes (redirects, replies, upload errors, profile location) | ✅ Done and live on Render: `e3439dc` |
| API test, every creator endpoint, live | ✅ **70 / 72 pass**. The 2 failures are items 3 and 5 below. |
| Browser test, every creator page, desktop + mobile | ✅ All real checks pass |
| Frontend live on clippit.click with the new code | ⏳ Not yet (item 1) |
| Full money loop (join → submit → earn → withdraw) | ⏳ Not tested with real data yet (item 5) |

---

## ✅ Done

- [x] Every creator screen wired to the real API:
  - dashboard, campaigns, campaign detail (join/leave)
  - submit → verification → verdicts → appeal
  - My clips, connected accounts
  - earnings, statement, wallet, withdraw, payout receipt, payout account
  - leaderboard, notifications, settings, security, public profile
  - support, disputes, legal, consent, receipt verification, account data/delete
- [x] Demo data ("Tobi On Cam", "GTBank · 6789", "₦18,400") removed. Screens show real data, empty states and readable errors.
- [x] Bugs fixed:
  - campaign pages returned 404 for real campaigns
  - the campaign list always showed demo data
  - joining reported success when it failed
  - withdraw never called the payout API
  - connected accounts read the wrong endpoint
  - OAuth and email links sent people to `http://localhost`
  - support and dispute replies didn't show until a reload
  - upload failures returned a blank 500
- [x] Brand accounts are kept out of the creator dashboard. Support, disputes and consent now require sign-in.
- [x] Backend redeployed on Render and retested live.

---

## ⏳ Still to do (in this order)

### 1. 🔴 Redeploy the frontend from `main`

**Why:** clippit.click still runs the old build with demo data.

**Do:** The frontend developer redeploys `main`, with `NEXT_PUBLIC_API_URL=https://clippit-5b5j.onrender.com` set in the hosting env.

**Confirm:** Sign in as a creator on clippit.click. You see your own name and real numbers, with no "Tobi On Cam".

- [ ] Done

---

### 2. 🔴 Turn background jobs on

**Why:** `BACKGROUND_JOBS_ENABLED=false` switches off:
- reading clip views
- turning views into earnings
- releasing held money to payable
- confirming bank transfers
- closing ended campaigns

Without these, **creators never earn**.

**Do:**
1. Render → Environment → `BACKGROUND_JOBS_ENABLED=true`
2. Keep **one** instance.
3. Move off the free plan (or add an always-on ping). Free instances sleep after 15 min, which stops the jobs and causes 30–50s cold starts.

**Confirm:** Render logs show `job:intelligence.poll`, and approved clips show `verified_views` going up.

- [ ] Done

---

### 3. 🔴 Fix the Cloudinary key (all uploads fail)

**Why:** Live test: `POST /uploads/images` → 502. Cloudinary says the key is *"missing permissions (actions=["create"])"*. That breaks:
- profile photos (onboarding and Settings)
- appeal evidence
- support and dispute attachments

**Do:**
1. Cloudinary console → Settings → API Keys → use the root key, or a key allowed to upload.
2. Render: set `CLOUDINARY_API_KEY` and `CLOUDINARY_API_SECRET` (keep `CLOUDINARY_CLOUD_NAME=doarhpvhv`).
3. Redeploy.

**Confirm:** Settings → add a profile photo → Save. It appears in the top bar.

- [ ] Done

---

### 4. 🔴 Make "Connect account" work (OAuth)

**Why:** Creators must connect the platform they post on before they can join or submit. Every redirect URI on Render still points to `http://localhost:8000`.

**Code (done):** the Connect button now only appears for a platform whose OAuth app credentials are set on Render. Threads is hidden because it isn't in PRD V1. Platforms without credentials show "Soon", so creators never land on a broken consent screen.

**Do:** Set these on Render, and add the **same URL, character for character** (https, no trailing slash) in each developer portal:

| Platform | Render env | Value | Credentials set? |
|---|---|---|---|
| TikTok | `TIKTOK_REDIRECT_URI` | `https://clippit-5b5j.onrender.com/social/tiktok/callback` | ✅ yes |
| X | `X_REDIRECT_URI` | `https://clippit-5b5j.onrender.com/social/x/callback` | ✅ yes (also needs `TWITTERAPI_IO_KEY` for views, ❌ empty) |
| Instagram | `INSTAGRAM_REDIRECT_URI` | `https://clippit-5b5j.onrender.com/social/instagram/callback` | ❌ `INSTAGRAM_APP_ID` / `_SECRET` empty |
| Facebook | `FACEBOOK_REDIRECT_URI` | `https://clippit-5b5j.onrender.com/social/facebook/callback` | ❌ `FACEBOOK_APP_ID` / `_SECRET` empty |
| YouTube | `YOUTUBE_REDIRECT_URI` | `https://clippit-5b5j.onrender.com/social/youtube/callback` | ❌ `YOUTUBE_CLIENT_ID` / `_SECRET` / `YOUTUBE_API_KEY` empty |
| Google sign-in | `GOOGLE_REDIRECT_URI` | `https://clippit-5b5j.onrender.com/auth/google/callback` | check |

Also check `FRONTEND_URL=https://clippit.click` (or leave it unset, since that's the default). After OAuth, the backend sends creators back to `FRONTEND_URL/dashboard/settings`.

Where each URL goes:
- **TikTok for Developers** → your app → Login Kit → Redirect URI. Products: Login Kit and the Display API, with scopes `user.info.basic` and `video.list`.
- **X Developer Portal** → your app → User authentication settings → Callback URI / Redirect URL. App type: Web App (confidential client). Scopes: `tweet.read`, `users.read` and `offline.access`.
- **Meta for Developers (Facebook)** → Facebook Login → Settings → Valid OAuth Redirect URIs. Permissions: `pages_show_list`, `pages_read_engagement`, `pages_read_user_content`.
- **Meta for Developers (Instagram)** → Instagram → API setup with Instagram login → Business login settings → OAuth redirect URIs. Permissions: `instagram_business_basic`, `instagram_business_manage_insights`. Use the **Instagram** app ID and secret here, which are different from the Facebook app ones.
- **Meta, both apps:** set Deauthorize callback `https://clippit-5b5j.onrender.com/webhooks/social/{facebook|instagram}/deauthorize` and Data deletion request URL `https://clippit-5b5j.onrender.com/webhooks/social/{facebook|instagram}/data-deletion`. Set Privacy Policy URL `https://www.clippit.click/legal/privacy`.
- **Google Cloud Console** → APIs & Services → Credentials → the OAuth client (Web application) → Authorized redirect URIs. Add both the YouTube and the Google sign-in URLs. Enable YouTube Data API v3. Scope: `youtube.readonly`. This is a sensitive scope, so the consent screen must be verified, or creators must be added as test users while it's in Testing.

- [ ] Set the redirect URIs on Render
- [ ] Register them in TikTok for Developers, X Developer Portal, Meta for Developers and Google Cloud Console
- [ ] Add the missing credentials (Instagram, Facebook, YouTube). Their Connect buttons appear automatically once the credentials are set.
- [ ] TikTok: submit the app for review, or add test creators as sandbox users
- [ ] Meta / X / Google: while an app is in development or testing mode, only the accounts added as testers can connect

**Confirm:** `/dashboard/accounts` → Connect TikTok → approve → you land on clippit.click Settings with "TikTok is connected".

---

### 5. 🔴 Run the full money loop once

**Why:** No funded campaign exists, so join, submit, earnings and withdrawal were only tested on their error paths.

**Do (after 1–4):**
1. Brand account → create a campaign on a platform the test creator has connected → fund it with a Paystack test card.
2. Creator → join → post a public clip → submit the link.
3. Brand approves it in Reviews (`COMPLIANCE_VERIFIER=manual`).
4. For a faster test, temporarily set `EARNINGS_HOLD_DAYS=0`.
5. Creator → add and verify a bank → withdraw → receipt.
6. **Tell me when the campaign is funded**, and I'll run the automated end-to-end test.

- [ ] Join works
- [ ] Submit → "Checking your clip" updates live
- [ ] Verdict shows the real requirement checks
- [ ] Earnings go from Held to Payable
- [ ] Withdraw shows the fee quote, then a receipt that goes Pending → Successful
- [ ] `/verify/<reference>` confirms the receipt

---

### 6. 🟠 Replace placeholder secrets, then go to production mode

**Why:** Anyone who knows the placeholder `JWT_SECRET` can forge a login.

| Env | Now | Set to |
|---|---|---|
| `JWT_SECRET` | `change_me_to_a_long_random_string` | new random 64+ character string |
| `INTERNAL_SERVICE_SECRET` | `change_me_shared_secret` | new random string |
| `PAYMENT_WEBHOOK_SECRET` | `change_me_webhook_secret` | new random string |
| `ENVIRONMENT` | `development` | `production` (only after the three above) |

Generate: `python -c "import secrets; print(secrets.token_urlsafe(64))"`. Changing `JWT_SECRET` signs everyone out once.

- [ ] Done

---

### 7. 🟠 Payments setup

- [ ] Paystack → Settings → API Keys & Webhooks → webhook URL `https://clippit-5b5j.onrender.com/webhooks/payments`. Without it, funded campaigns never go live.
- [ ] `PUBLIC_BASE_URL=https://clippit-5b5j.onrender.com` on Render
- [ ] Before real money: `PAYSTACK_SECRET_KEY` from `sk_test_…` to `sk_live_…`

---

### 8. 🟡 Product decisions (backend doesn't support these yet)

The UI is honest about each one today. Pick **build** or **leave as is**.

| Feature | Today | To make it real |
|---|---|---|
| ID verification (document, face check) | "Account checks" page: confirmed email, a connected account, a verified bank | KYC module + provider (Smile ID / Dojah) |
| Two-step login | Shown as "Coming soon" | TOTP endpoints |
| Download my data | Opens a Privacy support ticket | Export job + emailed link |
| "New campaigns in my lanes" / "Campaign closing" alerts | Toggles exist, **nothing sends them** | Job that emits these notifications |
| Public profile stats | Verified views, approved clips, content lanes | Add approval rate and campaign count to the API |

- [ ] Decided

---

### 9. 🟡 Clean-up (not blocking)

- [x] `WIRING.md` removed. This file replaces it.
- [ ] Old lint errors in files this work didn't touch:
  - `AuthPages.tsx`: apostrophes
  - setState in an effect: `AuthGuard.tsx`, `user-context.tsx`, `BrandScreens.tsx`
- [ ] Switch `RATE_LIMIT_STORAGE_URI` to Redis only if you ever run more than one instance.

---

## Done when

Items **1–7** are ticked and item **5** passes end to end on clippit.click.
