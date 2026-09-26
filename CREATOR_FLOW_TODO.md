# Creator flow — what's left before we mark it done

Status as of 26 Sep 2026. Code for every creator screen is wired to the live API and pushed (`b7f855d`, `e3439dc`).
What remains is mostly **configuration on Render and the platform developer portals**, plus one real end-to-end run with money.

Work top to bottom. Each item says why it matters, exactly what to do, and how to confirm it's fixed.

**Legend:** 🔴 blocks the creator flow · 🟠 needed before real users/money · 🟡 product decision or polish

---

## 1. 🔴 Deploy the latest backend on Render

**Why:** Three fixes aren't live yet:
- the new city/location field on profiles;
- OAuth and email links that currently send people to `http://localhost`;
- support and dispute replies that don't show up until a reload.

**Do:** Render → `clippit-api` → **Manual Deploy → Deploy latest commit** (must be `e3439dc` or later — *not* "Redeploy last build").

**Confirm:** In Settings → Creator profile, change "City or region", save, reload — it stays.

- [ ] Done

---

## 2. 🔴 Redeploy the frontend from `main`

**Why:** All the screen wiring is frontend code. Until it's redeployed, clippit.click still shows the old demo data.

**Do:** Frontend developer redeploys `main` (Vercel or wherever clippit.click is hosted). Make sure `NEXT_PUBLIC_API_URL=https://clippit-5b5j.onrender.com` is set in that project's env.

**Confirm:** Sign in as a creator on clippit.click. The dashboard shows *your* name and real numbers, with no "Tobi On Cam", "GTBank · 6789" or "₦18,400".

- [ ] Done

---

## 3. 🔴 Turn background jobs on

**Why:** With `BACKGROUND_JOBS_ENABLED=false`, none of these jobs ever run:

| Job | What it does | Every |
|---|---|---|
| `intelligence.poll` | reads views from TikTok/X/etc. for approved clips | 60s |
| `earnings.settle` | turns verified views into earnings | 5 min |
| `earnings.notify_payable` | moves held money to payable after the hold, and notifies | 15 min |
| `payouts.reconcile` | confirms bank transfers succeeded or failed | 2 min |
| `campaigns.sweep` | closes ended or empty campaigns | 5 min |
| `wallet.reconcile` | reconciles wallet movements | 2 min |

Without them a creator can get a clip approved and **never earn a naira**.

**Do:**
1. Render → Environment → set `BACKGROUND_JOBS_ENABLED=true`.
2. Keep the service on **one instance** (jobs run inside the API process; two instances would run them twice).
3. Move off the free plan (or add an always-on ping). Free instances sleep after 15 min idle, which stops the jobs and causes the 30–50s cold starts we saw during testing.

**Confirm:** Render logs show `job:intelligence.poll` activity. Once a clip is approved, `GET /creators/me/clips` shows `verified_views` climbing.

- [ ] Done

---

## 4. 🔴 Fix the Cloudinary key (uploads return an error)

**Why:** Every upload currently fails. Cloudinary rejects the key with *"Request forbidden due to missing permissions (actions=["create"])"*. That breaks:
- profile photo in onboarding and Settings
- evidence on appeals
- attachments on support tickets and disputes

**Do:**
1. Cloudinary console → **Settings → API Keys**.
2. Use the root key, or create a key whose role allows uploading to the Media Library.
3. On Render set `CLOUDINARY_API_KEY` and `CLOUDINARY_API_SECRET` to that key (keep `CLOUDINARY_CLOUD_NAME=doarhpvhv`).
4. Redeploy.

**Confirm:** Settings → pick a profile photo → Save profile. The photo appears in the top bar and on `/dashboard/profile`.

- [ ] Done

---

## 5. 🔴 Make "Connect account" work for real (OAuth redirect URIs)

**Why:** Creators must connect the platform they post on before they can **join** a campaign or **submit** a clip. Right now every `*_REDIRECT_URI` on Render points to `http://localhost:8000/...`, so the platform sends the creator back to localhost and the connection fails.

**Do:** For each platform you want live:

| Platform | Render env to set | Value |
|---|---|---|
| TikTok | `TIKTOK_REDIRECT_URI` | `https://clippit-5b5j.onrender.com/social/tiktok/callback` |
| X | `X_REDIRECT_URI` | `https://clippit-5b5j.onrender.com/social/x/callback` |
| Instagram | `INSTAGRAM_REDIRECT_URI` | `https://clippit-5b5j.onrender.com/social/instagram/callback` |
| Facebook | `FACEBOOK_REDIRECT_URI` | `https://clippit-5b5j.onrender.com/social/facebook/callback` |
| Threads | `THREADS_REDIRECT_URI` | `https://clippit-5b5j.onrender.com/social/threads/callback` |
| YouTube | `YOUTUBE_REDIRECT_URI` | `https://clippit-5b5j.onrender.com/social/youtube/callback` |

Then:
- [ ] Add the **same URL** as an allowed redirect/callback in each platform's developer portal (TikTok for Developers, X Developer Portal, Meta for Developers, Google Cloud Console for YouTube).
- [ ] **Instagram, Facebook, Threads and YouTube have no credentials set.** Either fill in `INSTAGRAM_APP_ID`/`_SECRET`, `FACEBOOK_APP_ID`/`_SECRET`, `THREADS_APP_ID`/`_SECRET` and `YOUTUBE_CLIENT_ID`/`_SECRET` (plus `YOUTUBE_API_KEY` for view counts), or tell me to hide those platforms. The UI shows a Connect button for all of them today, and it will fail for any without credentials.
- [ ] **TikTok:** a sandbox app only lets whitelisted test users connect. Submit the app for review, or add your test creators as sandbox users.
- [ ] **X views:** X metrics are read through twitterapi.io, and `TWITTERAPI_IO_KEY` is empty. Add a key or X clips won't collect views.

**Confirm:** `/dashboard/accounts` → Connect TikTok → approve → you land on `https://clippit.click/dashboard/settings` with a green "TikTok is connected" note, and the account shows "Connected".

- [ ] Done

---

## 6. 🔴 Run the full money loop once with a real funded campaign

**Why:** No live campaign exists on the backend, so the happy path was only tested on its error cases:
join → submit → verification → approval → earnings → withdraw → receipt.

**Do (after items 1–5):**
1. Sign up a **brand** account → create a campaign whose platform is one the test creator has connected → fund it with a Paystack test card.
2. Sign in as a **creator** → join it → post a real public clip → submit the link.
3. `COMPLIANCE_VERIFIER=manual`, so the **brand approves it** from its review queue (Brand → Reviews).
4. Wait for views to be read (item 3) and the hold period (5 days) to pass. For a faster test, temporarily set `EARNINGS_HOLD_DAYS=0`.
5. Creator → Payout account → add and verify a bank → Withdraw → receipt page.
6. Tell me when a funded campaign exists and I'll run the automated end-to-end test against it.

**Confirm:** every step below passes:
- [ ] Join works (or shows "Connect TikTok first")
- [ ] Submit goes to "Checking your clip" and updates live
- [ ] Verdict page shows the real requirement checks
- [ ] Earnings rows appear and move from Held to Payable
- [ ] Withdraw shows the server fee quote, then a receipt with status Pending → Successful
- [ ] `/verify/<reference>` confirms the receipt

---

## 7. 🟠 Replace placeholder secrets and go to production mode

**Why:** These are still the placeholder values from the template. Anyone who knows `JWT_SECRET` can forge a login for any account.

| Env | Current | Set to |
|---|---|---|
| `JWT_SECRET` | `change_me_to_a_long_random_string` | a new random 64+ character string |
| `INTERNAL_SERVICE_SECRET` | `change_me_shared_secret` | a new random string |
| `PAYMENT_WEBHOOK_SECRET` | `change_me_webhook_secret` | a new random string |
| `ENVIRONMENT` | `development` | `production` (only after the three above are set; the backend refuses to boot in production with placeholder secrets) |

Generate a value with: `python -c "import secrets; print(secrets.token_urlsafe(64))"`

⚠️ Changing `JWT_SECRET` signs everyone out once. That's expected.

- [ ] Done

---

## 8. 🟠 Payments: webhook and live key

**Do:**
- [ ] Paystack dashboard → Settings → API Keys & Webhooks → set the webhook URL to `https://clippit-5b5j.onrender.com/webhooks/payments`. Without it, funded campaigns never switch to live.
- [ ] Before real money: swap `PAYSTACK_SECRET_KEY` from `sk_test_…` to `sk_live_…`.
- [ ] Set `PUBLIC_BASE_URL=https://clippit-5b5j.onrender.com` on Render if it's still `http://localhost:8000`.

---

## 9. 🟡 Decide: features the UI mentions that the backend doesn't have

These aren't bugs. The backend simply doesn't support them yet, so I made the UI honest instead of faking them. Pick **build** or **leave as is** for each.

| Feature | What the UI does now | To make it real |
|---|---|---|
| Identity verification (ID document, face check) | `/dashboard/verification` shows "Account checks": confirmed email, a connected account, a verified bank. No document upload. | Backend KYC module + provider (e.g. Smile ID / Dojah) |
| Two-step login (2FA) | Security page shows it as "Coming soon" | Backend TOTP enrol/verify endpoints |
| "Download my data" | Opens a Privacy support ticket for the team to handle | Backend export job + emailed link |
| "New campaigns in my lanes" / "Campaign closing" notifications | Toggles exist but **nothing sends them** | Backend job that emits `new_campaign` and `campaign_closing` notifications |
| Public profile stats | Shows verified views, approved clips and content lanes (no approval rate or campaign count) | Add those fields to `/profiles/creators/{handle}` |
| Earnings statement date range | Filters by month on the client | Optional server-side date filter |

- [ ] Decisions made

---

## 10. 🟡 Clean-up (not blocking)

- [ ] `WIRING.md` is out of date. Replace it with this file or update it.
- [ ] Pre-existing lint errors not touched in this work: apostrophes in `components/auth/AuthPages.tsx`, setState-in-effect in `components/auth/AuthGuard.tsx`, `lib/user-context.tsx` and `components/brand/BrandScreens.tsx`.
- [ ] Rate limiting uses `memory://`. Fine for one instance; switch `RATE_LIMIT_STORAGE_URI` to Redis if you ever scale out.

---

## Done when

All of **1–8** are ticked and **6** passes end to end on clippit.click. Item **9** is a product call; the creator flow can ship with the current honest versions.
