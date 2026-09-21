# Performance & Trust Intelligence — boundary and contracts

**Owner:** Adam · **Status:** proposed, awaiting Koded's sign-off on §1 · **Date:** 2026-09-13

Operationalizes §7–§9, §16–§18 and §26 of *Clipit | Backend + Intelligence
Implementation Plan*. That document says what the intelligence subsystem is;
this one says exactly where it starts, where it stops, and what shape the
data is in when it crosses the line. It is the artifact of **Stage 0**: no
behaviour, just contracts, so that Adam and Koded can build in parallel
without discovering a disagreement three modules deep.

Machine-readable half of this document:

- `backend/core/platforms.py` — the canonical platform list
- `backend/integrations/social/base.py` — the adapter interface
- `backend/modules/intelligence/contracts.py` — everything that crosses the boundary

---

## 1. Boundary freeze

> ⚠️ **Unresolved:** `architecture/backend-modules.md` assigns these domains
> almost the other way round (Adam on campaigns/funding/submissions/admin,
> Koded on auth/intelligence/payout). The implementation plan is newer and is
> labelled the technical source of truth, so this document follows it. **The
> older document is marked superseded but the split is not final until Koded
> confirms it** — decision D1.

| Adam — Intelligence | Koded — Core backend |
|---|---|
| Platform adapters and all platform API logic | API conventions, routing, app skeleton |
| Ingestion and normalization | Postgres models and migrations for core entities |
| Metric snapshots and time-series storage | Auth, users, organisations |
| Performance features and analytics | Campaign lifecycle and business rules |
| Anomaly and trust engine | Creator and submission lifecycle |
| Comment analysis pipeline | Earnings, ledger, payout orchestration |
| The internal intelligence contract | Payment provider abstraction, reconciliation |

**Not assigned to either of us:** content verification (R2, FFmpeg, Deepgram,
LLM brief-compliance — phase 4 of the plan, listed as "team / assigned
backend+AI owner"). Flagged so it doesn't land on Intelligence by default —
decision D11.

**The hard rule, restated:** this module can determine and explain a result.
It must never hold bank credentials, retry a transfer, or move money.

## 2. What crosses the seam

**Into Intelligence, from Core:**

| What | Shape | Notes |
|---|---|---|
| A submission to work on | `SubmissionRef` | submission, campaign, creator, platform, URL |
| A creator's platform token | `GET /internal/social-accounts/{user_id}/{platform}/token` | already live in the auth module |

Submissions are Koded's table. Intelligence stores `submission_id` and reads
the rest back through a narrow interface rather than joining across domains —
which also lets Stage 2 run against a stub while his module is unfinished.

**Out of Intelligence, to Core:**

| What | Shape |
|---|---|
| How the content is performing | `PerformanceResult` |
| Whether that performance is credible | `TrustResult` |
| Both at once | `IntelligenceResult` |

Earnings bills on `features.incremental_views`. Everything else is context.

## 3. Canonical data model

Raw observations and derived values stay in separate tables, permanently.
Features get recomputed as the rules improve; observations never change.

```
SocialContent      one row per submitted post
  submission_id, campaign_id, creator_id,
  platform, platform_content_id, url, post_type, published_at

MetricSnapshot     append-only, one row per observation
  content_id, captured_at, views, likes, comments, shares,
  saves, reach, impressions, raw_metrics (JSONB), source

ContentFeature     derived, recomputable
  content_id, computed_at, incremental_views, view_velocity, ratios…

Comment            one row per fetched comment
  content_id, platform_comment_id, author_id, text, likes,
  replies, created_at, raw_data (JSONB)

TrustEvaluation    one row per trust run, with its signals
  content_id, evaluated_at, status, anomaly_score, signals (JSONB)
```

Three invariants, from §10 and §18 of the plan:

1. **Snapshots are append-only.** Never `UPDATE` a historical count. Growth
   rate is more informative than any single total, and an overwritten
   history cannot be audited.
2. **`NULL` ≠ `0`.** A metric the platform doesn't report is null. Writing
   zero reads as "nobody watched this" and would corrupt every ratio.
3. **Raw is retained.** The provider payload is stored alongside the
   normalized row so integration bugs are diagnosable after the fact.

As built in Stage 2 (`backend/modules/intelligence/models.py`, migration
`b7c41e05a9d2`), with three choices worth flagging to Koded:

- **No foreign keys to `submissions`, `campaigns` or `users`.** Those are
  his tables. We store the IDs and resolve through his internal API, so
  our migrations and his stay independent.
- **Enums are `VARCHAR` + `CHECK`, not native Postgres enum types.** Auth
  already owns a type named `platform` with four values; ours needs six.
  A checked varchar avoids the collision entirely and can be widened
  without the `ALTER TYPE` dance when YouTube lands. Unblocks us from D5.
- **`social_content.submission_id` is unique; `(platform,
  platform_content_id)` is not.** Re-ingesting a submission must reuse its
  row, but two creators submitting the *same post* is a trust signal we
  need to be able to see rather than a constraint violation.

Stage 4 adds `content_features` — one row per snapshot, holding what that
observation *means* (increment, velocity, ratios). Deliberately
disposable: `FeatureService.recompute_all()` rebuilds every row from the
snapshots, which is the point of never touching an observation. When the
velocity formula improves, history gets corrected with no refetching.

Stage 3 adds one more table, `content_tracking` — the poller's state, and
the only mutable table this module owns. One row per piece of content:
status, `next_poll_at`, failure counters, last error. `next_poll_at`
doubles as the work queue (`status = 'active' AND next_poll_at <= now()`),
so scheduling needs no separate queue system to operate.

## 3b. Polling model

| Post age | Interval |
|---|---|
| < 24h | 30 min |
| < 7 days | 2 hours |
| < 30 days | 12 hours |
| ≥ 30 days | tracking stops |

Front-loaded because a post's views are: the first day needs resolution,
a month-old post barely moves and polling it hourly just burns quota. The
30-day cap exists only because campaign end dates live in Koded's domain
— once his module can say "this one's done", `stop()` replaces the cap.

Work is **leased, not just read**: claiming a batch pushes `next_poll_at`
forward before any network call, inside one transaction, with
`FOR UPDATE SKIP LOCKED` on Postgres. Two workers therefore never poll the
same submission, and a worker that dies mid-poll doesn't strand its rows —
the lease expires and they come back. The cost is that a crash can lose a
single reading, which for a series about to be re-read is the right way
round.

Each submission is polled in **its own transaction**, and a poll never
raises: every failure becomes a recorded decision (retry with backoff,
stop, or dead-letter). One creator's dead token cannot roll back another
creator's snapshot or take down the tick.

## 4. Adapter contract

Interface: `backend/integrations/social/base.py`. Registry lookup mirrors
`modules/auth/providers`. No platform-specific request logic may exist
outside an adapter.

```python
platform: Platform
source: str                  # e.g. "tiktok.display_api" — stored as provenance
requires_creator_token: bool
supports_comments: bool

async def resolve_url(url) -> str | None
async def get_content(content_id, *, access_token=None) -> PlatformContent
async def get_metrics(content_id, *, access_token=None) -> PlatformMetrics
async def get_comments(content_id, *, access_token=None, cursor=None) -> CommentPage
```

Capability flags exist because the platforms genuinely differ and the plan
warns against an abstraction that hides that. Callers read the flag rather
than calling a method and catching an exception.

| Platform | Reads any public URL? | Views | Likes | Comment counts | Comment text | Validated |
|---|---|---|---|---|---|---|
| **TikTok** | No — creator token, own videos only | yes | yes | yes | **no** | `service-test/tt` |
| X | Yes — service key (twitterapi.io) | yes | yes | yes | yes | `service-test/X` |
| Instagram | No — creator token | yes | yes | yes | yes | `service-test/meta_insta` |
| Facebook | No — page token | impressions/reach | yes | yes | yes | `service-test/meta_fb` |
| Threads | No — creator token | yes | yes | yes | yes | `service-test/meta_threads` |
| YouTube | Yes — API key, no OAuth | yes | yes | yes | yes | not yet |

TikTok's constraint shapes Stage 1 and is worth stating plainly: the Display
API only returns the **authorized creator's own** videos. A submitted URL
that doesn't appear in that creator's video list cannot be read at all —
which means ownership verification is implicit for TikTok, and there is no
comment-text pipeline for it. Exact query semantics to confirm in Stage 1.

## 5. Internal API contract

```
POST /internal/submissions/{id}/metrics       trigger an observation now   ✅
GET  /internal/submissions/{id}/performance   -> PerformanceResult         ✅
GET  /internal/submissions/{id}/trust         -> TrustResult               ✅
POST /internal/submissions/{id}/trust/review  record a human's verdict     ✅
POST /internal/submissions/{id}/tracking/stop    Core closes / creator withdraws  ✅
POST /internal/submissions/{id}/tracking/resume  reopen after a mistaken close   ✅
GET  /internal/trust/rules                    active thresholds            ✅
GET  /internal/campaigns/{id}/performance     aggregate                    Stage 5+
GET  /internal/creators/{id}/performance      aggregate                    Stage 5+
```

**`/trust` reports; it never instructs.** There is no "block the payout"
in a `TrustResult` — only what was observed, the threshold it was
compared against, and a sentence that can be read to a creator during a
dispute. Whether `flagged` withholds money is earnings' and admin's call
(D22).

**`TrustResult.comments_sampled`** is how many comments the verdict was
allowed to see. Zero means we have no sample (TikTok, or not yet fetched)
— not that the thread is empty.

**`/trust/review` is the label factory.** Its `source` field is
mandatory: reviews drawn only from our own flagged queue can measure
precision and can never measure recall (D21).

Guarded by `X-Internal-Secret`, matching the convention the auth module
already uses.

**The POST talks to a platform; the GET never does.** A billing run uses
the GET, so nobody's payout waits on TikTok's uptime, and the read can't
be rate limited. The POST is for registering a new submission (send a
`SubmissionRef` body — 201, starts tracking) or forcing a fresh reading
before the next scheduled poll (no body needed).

Registration failures come back as HTTP errors, because a human is
waiting for an answer about the link they just pasted. A failure on a
*later* observation comes back as `200` with the reason in `tracking`,
because the submission still exists and its last known numbers are still
valid — what changed is that we've stopped watching. Every error body is
`{"detail": {"code": ..., "message": ...}}`, with the same codes as the
failure taxonomy in §6.

```json
{
  "submission_id": "…",
  "platform": "tiktok",
  "metrics": { "views": 12400, "likes": 930, "comments": 87, "shares": null },
  "features": { "incremental_views": 2100, "view_velocity_per_hour": 87.5 },
  "trust": {
    "status": "normal",
    "anomaly_score": 0.12,
    "signals": []
  },
  "provenance": {
    "platform": "tiktok",
    "source": "tiktok.display_api",
    "observed_at": "2026-09-13T10:00:00Z"
  }
}
```

`shares: null` in that example is the contract doing its job — TikTok
reports it, a platform that doesn't would send null rather than zero.

### Billing from this safely

`metrics.views` is the cumulative total as of `provenance.observed_at`.
`features.incremental_views` is relative to the *previous poll*, which
moves every thirty minutes — it's a velocity input, and a biller summing
it would double-count anything read twice and miss anything read late.

For money, pass `?since_snapshot_id=` — the `provenance.snapshot_id` from
the response last settled against — and read `features.billable_views`.
The same request asked twice gives the same answer, so a billing run is
safe to retry. That makes earnings' side of the contract one stored value
per submission (the snapshot it last paid for) and no arithmetic. This is
decision D18 and needs Koded's agreement.

Both deltas are floored at zero: platforms revise counts downward (TikTok
prunes bot views days later) and a negative must never reach a ledger.
The drop is still visible in the raw snapshots, where Stage 5 treats it
as the signal it is.

## 6. Failure taxonomy

Retry behaviour is part of the contract, not an implementation detail
(definition of done, item 4). Jobs branch on the exception class:

Implemented in `scheduling.decide()`; every row below has a test.

| Exception | Meaning | Job behaviour | Recorded code |
|---|---|---|---|
| `RateLimited` | Provider throttled us; `retry_after` when given | Wait exactly as long as the provider asked, else backoff | `rate_limited` |
| `UpstreamError` | 5xx, timeout, malformed body | Retry 1/2/4/8… min (capped at 1h), dead-letter after 6 | `upstream_error` |
| `TokenLookupFailed` | Our own auth module unreachable | Same as `UpstreamError` | `upstream_error` |
| `ContentUnavailable` | Private, deleted, geo-blocked, not the creator's | Stop polling, surface to product | `content_unavailable` |
| `ContentNotFound` | URL resolves to nothing | Fail the submission | `content_not_found` |
| `CreatorTokenExpired` / `MissingCreatorToken` | No usable token | Stop, ask creator to reconnect | `creator_reconnect_required` |
| `CapabilityNotSupported` | Platform can't answer this | Never retry, record and continue | `capability_not_supported` |
| `UrlNotRecognized` | Not a readable post URL | Fail the submission | `url_not_recognised` |
| anything else | A failure mode we haven't met | Retry, then dead-letter so it gets noticed | `unexpected_error` |

The default for an unknown failure is deliberately "slow down and get
noticed", never "quietly stop tracking".

Rate limiting is not theoretical: validating X on a free tier produced
`429` at one request per five seconds, and TikTok/Meta have their own
ceilings. Backoff belongs in the adapter and the poller, from day one.

## 7. Decisions register

Per §26 of the plan: record the decision, the owner and the date. An
unresolved decision written down is fixable; one buried in code is not.

| ID | Decision | Owner | Date | Status |
|---|---|---|---|---|
| D1 | Adam owns Intelligence, Koded owns core backend; `backend-modules.md` superseded | Adam + Koded | — | **open — needs Koded** |
| D2 | TikTok is the first production adapter | Adam | 2026-09-13 | decided |
| D3 | Intelligence ships inside the existing FastAPI monolith: `modules/intelligence/` + `integrations/social/` | Adam | 2026-09-13 | decided |
| D4 | Background job runtime: Inngest Python SDK vs Celery/RQ vs APScheduler | Adam | — | **open, but no longer blocking.** Scheduling policy and the worker are runtime-agnostic; a runtime only calls `coordinator.run_due()` on a timer. `modules/intelligence/worker.py` is a plain asyncio loop standing in until this is decided, and is the only file a decision replaces |
| D5 | `Platform` canonical in `core/platforms.py`; auth's DB enum migrated to match | Adam | 2026-09-19 | decided — `social_accounts.platform` now includes `x` and `youtube`; token path no longer 422s |
| D6 | Canonical metric names: views, likes, comments, shares, saves, reach, impressions; nullable; raw retained | Adam | 2026-09-13 | decided |
| D7 | Snapshots append-only; polling cadence policy by content age | Adam | 2026-09-14 | decided — 30min / 2h / 12h by age, stop at 30 days (see §3b) |
| D8 | X metrics via twitterapi.io (third party) behind the adapter | Adam | 2026-09-13 | decided — cost/ToS to revisit before launch |
| D9 | Comments fetched continuously or sampled | Adam | 2026-09-19 | decided — sampled: 3 pages / 200 comments per successful observation. Upsert by platform comment id. TikTok is a no-op (`supports_comments=False`) |
| D10 | Trust score formula and first thresholds | Adam | — | decided (provisional) — severity-weighted sum capped at 1.0, any `critical` signal flags on its own (never averaged away). Metric rules plus three comment-text rules (near-duplicate, burst, author flood); no sentiment |
| D20 | Trust thresholds must be replaced by empirical per-platform percentiles | Adam | — | open — needs production traffic. Use median/MAD, not mean/stdev: the population contains the fraud we're detecting and a few extreme cases would drag a mean until the detector stops detecting |
| D21 | Admin must send random audits, not only review what we flagged | Adam + Koded | — | open — `POST /trust/review` requires `source`; without a trickle of `random_audit` on unflagged submissions we can measure precision but never recall, and any future model just learns to imitate today's rules |
| D22 | Who acts on a flag | Koded | 2026-09-21 | **implemented, needs Koded's confirmation.** A `flagged` trust status pauses *accrual* for that submission (views are still recorded; nothing new is owed) and resumes on its own when the flag clears. Money already accrued is untouched — it is inside the 5-day hold, and an admin can act on it. Blocked accounts are listed at `GET /admin/earnings/blocked` |
| D11 | Owner of content verification (R2/FFmpeg/Deepgram/LLM) | Team | — | **open — unassigned** |
| D12 | Product name spelled "Clippit" (repo) vs "Clipit" (plan doc) | Team | — | open — cosmetic but pick one |
| D13 | Retry/backoff lives in the job layer, not in adapters. Adapters raise `RateLimited`/`UpstreamError` carrying `retry_after`; only the poller sleeps | Adam | 2026-09-14 | decided |
| D14 | Intelligence reads creator tokens over auth's `/internal/social-accounts/…/token` endpoint behind a `TokenSource` port — never by importing auth's models or querying `social_accounts` | Adam | 2026-09-14 | decided — swap to an in-process impl later without touching ingestion |
| D15 | A re-read with identical counters inside 60s is not stored as a new snapshot; anything that moved, or any reading after the window, always is | Adam | 2026-09-14 | decided — window may need tuning once Stage 3 sets cadence |
| D16 | Cadence tiers, the 6-failure dead-letter threshold and the 5-minute claim lease are first guesses, not measured | Adam | — | open — revisit against real campaign traffic; no production data exists to tune against yet |
| D17 | Core tells us when to stop tracking (campaign ended, submission withdrawn) via `stop()`/`resume()`; until then a 30-day age cap stands in | Adam + Koded | 2026-09-19 | decided — `POST /internal/submissions/{id}/tracking/stop` and `/resume`; withdraw and campaign close call stop. 30-day cap remains the backstop |
| D18 | Earnings bills from `billable_views` against a caller-supplied `since_snapshot_id`, not from `incremental_views`. Earnings stores the last snapshot it settled; we stay stateless about money | Adam + Koded | 2026-09-21 | **implemented differently, needs Adam's ack.** Core bills from cumulative `metrics.views` (whole thousands: `floor(views/1000) − thousands already billed`) and records `provenance.snapshot_id` on every earning entry. Same answer, no `since_snapshot_id` state to keep, and partial thousands roll forward instead of being floored away poll by poll (900 + 900 views is one thousand, not zero twice). `billable_views` is unused by Core; harmless to keep |
| D19 | Features are stored per snapshot and recomputable; the trust engine reads the stored series, never recomputes ad hoc, so a payout and an audit always see the same numbers | Adam | 2026-09-14 | decided |
| D23 | Payment provider (Squad vs Paystack; frontend copy says Payaza) | Team | — | **open.** Everything money-moving sits behind `integrations/payments.PaymentProvider`. Default is a deterministic `sandbox`; the app refuses to start with `ENVIRONMENT=production` and the sandbox. A real adapter is one file |
| D24 | A campaign opens only when its funding is confirmed | Koded | 2026-09-21 | decided — `POST /campaigns/{id}/activate` requires a confirmed order; the brand's own "I have funded the pot" only asks the provider. Terms lock when funding starts |
| D25 | Brief verification before D11 has an owner | Koded | 2026-09-21 | decided (interim) — `submissions.verification.Verifier` interface; default sends every clip to the brand's review queue, so nothing earns until a person approves. A campaign with no requirements approves outright. An automated verifier replaces the default without touching anything else |
| D26 | Money is `Decimal`/`NUMERIC(14,2)`, earnings are append-only, and a payout reserves before it sends | Koded | 2026-09-21 | decided — payable = entries past the hold − live allocations; a failed transfer returns money by ceasing to count, never by editing rows |

## 8. Stage roadmap

| Stage | Scope | Exit condition |
|---|---|---|
| **0. Contracts** | This document + the three contract files | Koded can code against the contract without knowing any platform API |
| **1. Adapter layer** ✅ | Interface + TikTok adapter, ported from `service-test/tt`. No DB, no routes | A real TikTok URL yields canonical metrics in a test, raw preserved |
| **2. Ingestion & snapshots** ✅ | Schema, migration, normalizer, idempotent append-only writes | Ingesting twice yields two snapshots; nothing overwritten |
| **3. Polling & jobs** ✅ | Job runtime, cadence by content age, backoff, retries, dead-letter | One submission grows a time series over hours, unattended |
| **4. Performance features** ✅ | Feature table + `/internal/submissions/{id}/performance` | Earnings can bill from our output alone |
| **5. Trust & anomaly v1** ✅ | Explainable rules, scores, signals, review outcomes as labels + `/trust` | Every flag can be explained to a human in the admin queue |
| **6. Comment intelligence** ✅ | Comment ingestion, near-duplicate/timing/coordination signals | Comment evidence appears in a trust result; sentiment stays out |

Stages 1–4 are the spine — URL to a billable number. 5 and 6 are the trust
work and can land after the money path is proven.

## 9. Definition of done

From §22 of the plan, applied to every stage above:

1. The owning module is unambiguous.
2. The input/output contract is written down.
3. Data sits in its source-of-truth location — observations and derived
   features never in the same table.
4. Failure and retry behaviour is defined for every external dependency.
5. There's at least one reproducible verification path.
6. The consumer can use it without knowing how it works inside.
7. Important actions are observable in logs/events, with audit records
   where money or trust decisions are involved.
