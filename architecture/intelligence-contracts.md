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

## 4. Adapter contract

Interface: `backend/integrations/social/base.py`. Registry lookup mirrors
`modules/auth/providers`. No platform-specific request logic may exist
outside an adapter.

```python
platform: Platform
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
POST /internal/submissions/{id}/metrics       trigger an observation now
GET  /internal/submissions/{id}/performance   -> PerformanceResult
GET  /internal/submissions/{id}/trust         -> TrustResult
GET  /internal/campaigns/{id}/performance     aggregate (Stage 4+)
GET  /internal/creators/{id}/performance      aggregate (Stage 4+)
```

Guarded by `X-Internal-Secret`, matching the convention the auth module
already uses.

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

## 6. Failure taxonomy

Retry behaviour is part of the contract, not an implementation detail
(definition of done, item 4). Jobs branch on the exception class:

| Exception | Meaning | Job behaviour |
|---|---|---|
| `RateLimited` | Provider throttled us; `retry_after` when given | Back off and retry |
| `UpstreamError` | 5xx, timeout, malformed body | Retry with backoff, then dead-letter |
| `ContentUnavailable` | Private, deleted, geo-blocked, not the creator's | Stop polling, surface to product |
| `ContentNotFound` | URL resolves to nothing | Fail the submission |
| `CreatorTokenExpired` | OAuth token dead | Stop, ask creator to reconnect |
| `CapabilityNotSupported` | Platform can't answer this | Never retry, record and continue |

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
| D4 | Background job runtime: Inngest Python SDK vs Celery/RQ vs APScheduler | Adam | — | open — needed by Stage 3 |
| D5 | `Platform` canonical in `core/platforms.py`; auth's DB enum migrated to match | Koded | — | open — needs his migration |
| D6 | Canonical metric names: views, likes, comments, shares, saves, reach, impressions; nullable; raw retained | Adam | 2026-09-13 | decided |
| D7 | Snapshots append-only; polling cadence policy by content age | Adam | — | append-only decided; cadence open, Stage 3 |
| D8 | X metrics via twitterapi.io (third party) behind the adapter | Adam | 2026-09-13 | decided — cost/ToS to revisit before launch |
| D9 | Comments fetched continuously or sampled | Adam | — | open — Stage 6 |
| D10 | Trust score formula and first thresholds | Adam | — | open — Stage 5 |
| D11 | Owner of content verification (R2/FFmpeg/Deepgram/LLM) | Team | — | **open — unassigned** |
| D12 | Product name spelled "Clippit" (repo) vs "Clipit" (plan doc) | Team | — | open — cosmetic but pick one |

## 8. Stage roadmap

| Stage | Scope | Exit condition |
|---|---|---|
| **0. Contracts** | This document + the three contract files | Koded can code against the contract without knowing any platform API |
| **1. Adapter layer** | Interface + TikTok adapter, ported from `service-test/tt`. No DB, no routes | A real TikTok URL yields canonical metrics in a test, raw preserved |
| **2. Ingestion & snapshots** | Schema, migration, normalizer, idempotent append-only writes | Ingesting twice yields two snapshots; nothing overwritten |
| **3. Polling & jobs** | Job runtime, cadence by content age, backoff, retries, dead-letter | One submission grows a time series over hours, unattended |
| **4. Performance features** | Feature table + `/internal/submissions/{id}/performance` | Earnings can bill from our output alone |
| **5. Trust & anomaly v1** | Explainable rules, scores, signals, review outcomes as labels + `/trust` | Every flag can be explained to a human in the admin queue |
| **6. Comment intelligence** | Comment ingestion, near-duplicate/timing/coordination signals | Comment evidence appears in a trust result; sentiment stays out |

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
