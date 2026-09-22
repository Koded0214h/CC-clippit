# Clippit production screen inventory

This is the locked remainder for the current product build. The number does not expand when a backend endpoint, modal, empty state, loading state, validation state, or responsive layout is discovered. Those are implementation states inside the screens below.

## Locked totals

| Category | Remaining | Delivery |
| --- | ---: | --- |
| Customer-facing | 29 | Built in the current customer-completion pass |
| Admin and operations | 32 | Next product pass |
| **Total remaining** | **61** | **Locked** |

The 51 routes that existed before this pass are not counted again. Drawers, filters, confirmations, upload states, success states and mobile layouts are not counted as additional screens.

## Customer-facing screens — 29

### Support and disputes — 8

| # | Route | Screen | Purpose |
| ---: | --- | --- | --- |
| 1 | `/help` | Help centre | Search common answers and enter support flows. |
| 2 | `/help/[slug]` | Help article | Read one support guide with related actions. |
| 3 | `/support/tickets` | Support tickets | View open and resolved conversations. |
| 4 | `/support/tickets/new` | New support ticket | Contact support with a structured issue. |
| 5 | `/support/tickets/[id]` | Support conversation | Read and reply to a support thread. |
| 6 | `/disputes` | Disputes | Track formal money and decision disputes. |
| 7 | `/disputes/new` | Open dispute | Submit a structured claim and evidence. |
| 8 | `/disputes/[id]` | Dispute case | Follow evidence, deadlines and decisions. |

### Privacy, legal and public trust — 6

| # | Route | Screen | Purpose |
| ---: | --- | --- | --- |
| 9 | `/account/data` | Your data | Request and track a personal data export. |
| 10 | `/account/delete` | Delete account | Review blockers and request safe account deletion. |
| 11 | `/legal` | Legal centre | Find the documents governing the account and campaigns. |
| 12 | `/legal/[slug]` | Legal document | Read a versioned legal document. |
| 13 | `/consent/update` | Updated terms | Review and accept a newly required document version. |
| 14 | `/verify/[reference]` | Receipt verification | Verify a Clippit transaction reference publicly. |

### Creator completion — 6

| # | Route | Screen | Purpose |
| ---: | --- | --- | --- |
| 15 | `/dashboard/verification` | Creator verification | Explain verification status and requirements. |
| 16 | `/dashboard/verification/identity` | Identity details | Collect the creator's legal identity. |
| 17 | `/dashboard/verification/documents` | Identity document | Capture and validate an identity document. |
| 18 | `/dashboard/verification/status` | Verification status | Track checks, corrections and approval. |
| 19 | `/dashboard/earnings/statement` | Earnings statement | Filter and download an auditable earnings statement. |
| 20 | `/creators/[handle]` | Public creator profile | Share approved work and creator information publicly. |

### Brand completion — 9

| # | Route | Screen | Purpose |
| ---: | --- | --- | --- |
| 21 | `/brand/verification` | Business verification | Explain verification status and requirements. |
| 22 | `/brand/verification/business` | Business details | Collect legal organisation and representative details. |
| 23 | `/brand/verification/documents` | Business documents | Upload registration and address evidence. |
| 24 | `/brand/verification/status` | Business verification status | Track checks, corrections and approval. |
| 25 | `/brand/team` | Team members | Manage workspace access and roles. |
| 26 | `/brand/team/invite` | Invite team member | Invite a collaborator with a defined role. |
| 27 | `/brand/billing` | Billing and invoices | Review billing identity, charges and invoices. |
| 28 | `/brand/invoices/[id]` | Invoice | View and download one official invoice. |
| 29 | `/brand/campaigns/[slug]/refund` | Campaign refund | Review and request return of an unused campaign balance. |

## Admin and operations screens — 32

### Access and command centre — 2

| # | Route | Screen |
| ---: | --- | --- |
| 30 | `/admin/login` | Operator sign in |
| 31 | `/admin` | Operations command centre |

### Customers and verification — 6

| # | Route | Screen |
| ---: | --- | --- |
| 32 | `/admin/users` | Customer directory |
| 33 | `/admin/users/[id]` | Customer account detail |
| 34 | `/admin/creators/verifications` | Creator KYC queue |
| 35 | `/admin/creators/verifications/[id]` | Creator KYC review |
| 36 | `/admin/brands/verifications` | Business KYB queue |
| 37 | `/admin/brands/verifications/[id]` | Business KYB review |

### Campaigns and submissions — 4

| # | Route | Screen |
| ---: | --- | --- |
| 38 | `/admin/campaigns` | Campaign oversight |
| 39 | `/admin/campaigns/[slug]` | Campaign operations detail |
| 40 | `/admin/submissions` | Submission moderation queue |
| 41 | `/admin/submissions/[id]` | Submission evidence review |

### Support and disputes — 4

| # | Route | Screen |
| ---: | --- | --- |
| 42 | `/admin/support` | Support queue |
| 43 | `/admin/support/[id]` | Support case workspace |
| 44 | `/admin/disputes` | Dispute queue |
| 45 | `/admin/disputes/[id]` | Dispute resolution workspace |

### Money operations — 6

| # | Route | Screen |
| ---: | --- | --- |
| 46 | `/admin/payouts` | Payout operations |
| 47 | `/admin/payouts/[id]` | Payout investigation |
| 48 | `/admin/refunds` | Refund operations |
| 49 | `/admin/refunds/[id]` | Refund investigation |
| 50 | `/admin/ledger` | Finance ledger |
| 51 | `/admin/reconciliation` | Provider reconciliation |

### Trust, providers and delivery — 5

| # | Route | Screen |
| ---: | --- | --- |
| 52 | `/admin/risk` | Risk and fraud queue |
| 53 | `/admin/risk/[id]` | Risk case detail |
| 54 | `/admin/social-connections` | Social provider health |
| 55 | `/admin/webhooks` | Webhook delivery monitor |
| 56 | `/admin/notifications` | Notification delivery monitor |

### Operators, access and system — 5

| # | Route | Screen |
| ---: | --- | --- |
| 57 | `/admin/operators` | Operator directory |
| 58 | `/admin/operators/invite` | Invite operator |
| 59 | `/admin/roles` | Roles and permissions |
| 60 | `/admin/audit` | Immutable audit log |
| 61 | `/admin/system` | System health and runtime configuration |

## Review rule

The customer review index is available at `/review/customer-screens`. It is a development-only directory and is not part of the 61-screen product count.
