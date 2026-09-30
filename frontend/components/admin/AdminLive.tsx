"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { adminApi } from "@/lib/api/admin";
import { errorMessage } from "@/lib/api/client";
import { openOpsSocket, type OpsSocketState } from "@/lib/api/opsSocket";
import { money } from "@/lib/product";
import { ClippitLoader } from "@/components/ui/ClippitLoader";
import { AdminButton, AdminHeading, AdminStatus, titleCase } from "./AdminScreens";

type RecordData = Record<string, unknown>;
type QueueKind = "users" | "creator-verifications" | "brand-verifications" | "campaigns" | "submissions" | "support" | "disputes" | "payouts" | "refunds" | "risk" | "funding" | "earnings" | "reports" | "flagged" | "random-audits";
type DetailKind = "user" | "creator-verification" | "brand-verification" | "campaign" | "submission" | "support" | "dispute" | "payout" | "refund" | "risk" | "ledger" | "earning" | "report" | "audit";
const str = (value: unknown) => value == null ? "—" : String(value);
const record = (value: unknown) => value as RecordData;
const records = (value: unknown) => value as RecordData[];
const pageSize = 50;

function useRemote<T>(load: () => Promise<T>) {
  const [revision, setRevision] = useState(0);
  const refresh = useCallback(() => setRevision((v) => v + 1), []);
  // A fresh token per request; a result only counts for the request that made it.
  const token = useMemo(() => ({ load, revision }), [load, revision]);
  const [result, setResult] = useState<{ token: object | null; data: T | null; error: string }>({ token: null, data: null, error: "" });
  useEffect(() => {
    let alive = true;
    load()
      .then((value) => { if (alive) setResult({ token, data: value, error: "" }); })
      .catch((err) => { if (alive) setResult((prev) => ({ token, data: prev.data, error: errorMessage(err, "Could not load this information. Please try again.") })); });
    return () => { alive = false; };
  }, [load, token]);
  const settled = result.token === token;
  const setData = useCallback((update: (previous: T | null) => T | null) => setResult((prev) => ({ ...prev, data: update(prev.data) })), []);
  // Old data stays on screen while reloading, so a form's success message
  // isn't unmounted by the refresh it triggered.
  return { data: result.data, error: settled ? result.error : "", loading: !settled && result.data === null, refresh, setData };
}

function RemoteState({ loading, error, retry, children }: { loading: boolean; error: string; retry: () => void; children: ReactNode }) {
  if (loading) return <ClippitLoader contained tone="ink" label="Loading operations" note="Reading current records." />;
  if (error) return <section className="admin-live-notice" role="alert"><h2>Unable to load records</h2><p>{error}</p><AdminButton onClick={retry}>Try again</AdminButton></section>;
  return <>{children}</>;
}

function Fields({ data }: { data: unknown }) {
  if (data == null) return <span>Not available</span>;
  if (Array.isArray(data)) return data.length ? <div className="admin-record-list">{data.map((v, i) => <div key={i}><Fields data={v} /></div>)}</div> : <span>None</span>;
  if (typeof data !== "object") return <span>{typeof data === "boolean" ? data ? "Yes" : "No" : str(data)}</span>;
  return <dl className="admin-record-fields">{Object.entries(record(data)).map(([key, value]) => <div key={key}><dt>{titleCase(key)}</dt><dd>{key === "url" && typeof value === "string" && /^https?:\/\//.test(value) ? <a href={value} target="_blank" rel="noreferrer">Open submitted content</a> : <Fields data={value} />}</dd></div>)}</dl>;
}

type Input = { name: string; label: string; type?: "text" | "number" | "email" | "textarea" | "checkboxes"; options?: string[]; optionLabels?: Record<string, string>; minLength?: number; maxLength?: number; optional?: boolean; value?: string; min?: number; max?: number };
type Action = { label: string; fields?: Input[]; run: (values: Record<string, string>) => Promise<unknown>; confirm?: string };
function ActionForm({ action, done }: { action: Action; done?: () => void }) {
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  return <form className="admin-live-form" onSubmit={async (event) => {
    event.preventDefault(); if (pending.current) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    const values = Object.fromEntries([...new Set(data.keys())].map((k) => [k, data.getAll(k).map((v) => String(v).trim()).join(",")]));
    const missing = action.fields?.find((field) => field.type === "checkboxes" && !field.optional && !values[field.name]);
    if (missing) { setError(`Choose at least one ${missing.label.toLowerCase()}.`); return; }
    if (action.confirm && !window.confirm(action.confirm)) return;
    pending.current = true; setBusy(true); setError(""); setSuccess("");
    try { const result = await action.run(values); setSuccess(result && typeof result === "object" && "processed" in result ? `Completed · ${str(result.processed)} processed` : "Saved successfully."); done?.(); }
    catch (err) { setError(errorMessage(err)); }
    finally { pending.current = false; setBusy(false); }
  }}><h3>{action.label}</h3>{action.fields?.map((field) => field.type === "checkboxes" ? <fieldset key={field.name} className="admin-live-checks"><legend>{field.label}</legend>{field.options?.map((option) => <label key={option}><input type="checkbox" name={field.name} value={option} defaultChecked={field.value?.split(",").includes(option)} disabled={busy} />{field.optionLabels?.[option] ?? titleCase(option)}</label>)}</fieldset> : <label key={field.name}><span>{field.label}</span>{field.options ? <select name={field.name} defaultValue={field.value ?? field.options[0]} disabled={busy}>{field.options.map((option) => <option key={option} value={option}>{field.optionLabels?.[option] ?? (option ? titleCase(option) : "Unassigned")}</option>)}</select> : field.type === "textarea" ? <textarea name={field.name} required={!field.optional} minLength={field.minLength} maxLength={field.maxLength ?? 1000} disabled={busy} defaultValue={field.value} /> : <input name={field.name} type={field.type ?? "text"} required={!field.optional} minLength={field.minLength} maxLength={field.maxLength} min={field.min} max={field.max} step={field.type === "number" ? "any" : undefined} defaultValue={field.value} disabled={busy} />}</label>)}{error && <p role="alert">{error}</p>}{success && <p role="status">{success}</p>}<AdminButton type="submit" disabled={busy}>{action.label}</AdminButton></form>;
}
const note: Input = { name: "note", label: "Reason and evidence", type: "textarea", minLength: 5, maxLength: 300 };

async function download(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob); const a = document.createElement("a"); a.href = url; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
const titles: Record<QueueKind, string> = { users: "Customers", "creator-verifications": "Creator verification", "brand-verifications": "Business verification", campaigns: "Campaign oversight", submissions: "Submission moderation", support: "Support queue", disputes: "Disputes", payouts: "Payout operations", refunds: "Refund operations", risk: "Earnings blocked by trust", funding: "Campaign funding", earnings: "Earning entries", reports: "Content reports", flagged: "Flagged submissions", "random-audits": "Random submission audits" };
const routeBase: Partial<Record<QueueKind, string>> = { users: "users", "brand-verifications": "brands/verifications", campaigns: "campaigns", submissions: "submissions", support: "support", disputes: "disputes", payouts: "payouts", refunds: "refunds", risk: "submissions", funding: "ledger", earnings: "earnings", reports: "reports", flagged: "submissions", "random-audits": "submissions" };
const filterOptions: Partial<Record<QueueKind, string[]>> = { users: ["creator", "organisation", "admin"], campaigns: ["draft", "pending_funding", "active", "closed"], funding: ["awaiting_payment", "awaiting_confirmation", "confirmed", "cancelled", "failed"], support: ["open", "closed"], disputes: ["open", "awaiting_customer", "resolved", "withdrawn"], payouts: ["pending", "processing", "succeeded", "failed"], refunds: ["pending", "processing", "succeeded", "failed"], reports: ["open", "resolved"], submissions: ["checking", "needs_review", "approved", "rejected", "appealed"] };

async function queueLoad(kind: QueueKind, offset: number, filter: string, query: string): Promise<RecordData[]> {
  const params = { limit: pageSize, offset };
  let result: unknown;
  switch (kind) {
    case "users": result = await adminApi.listUsers({ ...params, role: filter || undefined, q: query || undefined }); break;
    case "brand-verifications": result = await adminApi.listUsers({ ...params, role: "organisation", q: query || undefined }); break;
    case "campaigns": result = await adminApi.listCampaigns({ ...params, status: filter || undefined }); break;
    case "submissions": result = await adminApi.allSubmissions({ ...params, verification_status: filter || undefined }); break;
    case "flagged": result = await adminApi.flaggedSubmissions(params); break;
    case "random-audits": result = await adminApi.randomAudits({ limit: 100 }); break;
    case "support": result = await adminApi.supportQueue({ ...params, status: filter || undefined }); break;
    case "disputes": result = await adminApi.disputeQueue({ ...params, status: filter || undefined }); break;
    case "payouts": result = await adminApi.listPayouts({ ...params, status_filter: filter || undefined }); break;
    case "refunds": result = await adminApi.listRefunds({ ...params, status: filter || undefined }); break;
    case "risk": result = await adminApi.blockedAccounts(); break;
    case "funding": result = await adminApi.listFunding({ limit: 200, status_filter: filter || undefined }); break;
    case "earnings": result = await adminApi.listEarningEntries(params); break;
    case "reports": result = await adminApi.reportQueue({ ...params, status: filter || undefined }); break;
    default: return [];
  }
  return records(result);
}
function QueueRows({ rows, kind }: { rows: RecordData[]; kind: QueueKind }) {
  return <div className="admin-live-table"><table><thead><tr><th>Record</th><th>Subject</th><th>Status</th><th>Value / context</th><th>Created</th></tr></thead><tbody>{rows.map((row) => {
    const id = str(row.id ?? row.submission_id);
    const amount = row.amount ?? row.total ?? row.accrued;
    return <tr key={id}><td><Link href={`/admin/${routeBase[kind]}/${kind === "campaigns" ? row.slug : id}`}>{str(row.reference ?? id)}</Link></td><td>{str(row.full_name ?? row.title ?? row.subject ?? row.creator_name ?? row.campaign_title ?? row.reason ?? row.type ?? row.platform ?? row.kind)}<small>{str(row.email ?? row.organisation_name ?? row.campaign_id ?? row.creator_id)}</small></td><td>{str(row.verification_status ?? row.status ?? (row.suspended === undefined ? row.reason ?? "—" : row.suspended ? "Suspended" : "Active"))}</td><td>{amount == null ? row.pot != null ? money(Number(row.pot) - Number(row.spent)) : str(row.priority ?? row.target_type ?? row.role ?? row.cumulative_views) : money(Number(amount))}</td><td>{row.created_at || row.initiated_at || row.accrued_at ? new Date(str(row.created_at ?? row.initiated_at ?? row.accrued_at)).toLocaleString() : "—"}</td></tr>;
  })}</tbody></table>{!rows.length && <p className="admin-live-notice">No records found.</p>}</div>;
}

export function AdminQueueScreen({ kind }: { kind: QueueKind }) {
  const [offset, setOffset] = useState(0), [filter, setFilter] = useState(""), [query, setQuery] = useState(""), [search, setSearch] = useState("");
  const load = useCallback(() => queueLoad(kind, offset, filter, search), [kind, offset, filter, search]);
  const state = useRemote(load);
  const paginated = !["risk", "funding", "random-audits", "creator-verifications"].includes(kind);
  if (kind === "creator-verifications") return <div className="admin-page"><AdminHeading title={titles[kind]} /><section className="admin-live-notice"><h2>Identity review is not available</h2><p>The backend does not provide an admin identity-verification queue or approval action yet.</p><Link href="/admin/users">View customer accounts</Link></section></div>;
  return <div className="admin-page"><AdminHeading title={titles[kind]} copy={kind === "brand-verifications" ? "Organisation accounts. Open an account to verify or revoke business verification." : kind === "funding" ? "Latest 200 funding orders. Open an order awaiting payment or confirmation to confirm the money arrived." : kind === "random-audits" ? "Up to 100 submissions selected by the trust service." : "Current backend records."} action={<AdminButton onClick={state.refresh}>Refresh</AdminButton>} />
    <nav className="admin-live-links">{kind === "submissions" && <><Link href="/admin/flagged">Flagged submissions</Link><Link href="/admin/random-audits">Random audits</Link></>}{kind === "risk" && <Link href="/admin/trust">Trust rules</Link>}{kind === "payouts" && <Link href="/admin/reconciliation">Reconciliation tools</Link>}</nav>
    <form className="admin-live-filters" onSubmit={(event) => { event.preventDefault(); setOffset(0); setSearch(query); }}><label>{["users", "brand-verifications"].includes(kind) ? "Search customers" : "Search loaded records"}<input value={query} onChange={(e) => setQuery(e.target.value)} /></label>{filterOptions[kind] && <label>{kind === "users" ? "Role" : "Status"}<select value={filter} onChange={(e) => { setOffset(0); setFilter(e.target.value); }}><option value="">All</option>{filterOptions[kind]?.map((v) => <option key={v} value={v}>{titleCase(v)}</option>)}</select></label>}<button type="submit">Search</button></form>
    <RemoteState {...state} retry={state.refresh}><QueueRows kind={kind} rows={(state.data ?? []).filter((row) => ["users", "brand-verifications"].includes(kind) || !search || JSON.stringify(row).toLowerCase().includes(search.toLowerCase()))} />{paginated && <div className="admin-live-pagination"><button disabled={!offset} onClick={() => setOffset(Math.max(0, offset - pageSize))}>Previous</button><span>Page {offset / pageSize + 1} · {state.data?.length ?? 0} records</span><button disabled={(state.data?.length ?? 0) < pageSize} onClick={() => setOffset(offset + pageSize)}>Next</button></div>}</RemoteState>
  </div>;
}

async function detailLoad(kind: DetailKind, id: string): Promise<unknown> {
  switch (kind) {
    case "user": case "brand-verification": return adminApi.userDetail(id);
    case "campaign": return adminApi.campaignDetail(id);
    case "submission": case "risk": return adminApi.submissionDetail(id);
    case "support": return adminApi.ticketDetail(id);
    case "dispute": return adminApi.disputeDetail(id);
    case "report": return adminApi.reportDetail(id);
    case "earning": return adminApi.earningEntryDetail(id);
    case "audit": return adminApi.auditDetail(id);
    case "payout": case "refund": case "ledger": return adminApi.ledgerEntryDetail(id);
    default: return null;
  }
}
type OperatorOption = { id: string; full_name: string; email: string };

function assigneeField(operators: OperatorOption[], current: unknown): Input {
  const options = ["", ...operators.map((o) => o.id)];
  const labels = Object.fromEntries([["", "Unassigned"], ...operators.map((o) => [o.id, `${o.full_name} · ${o.email}`])]);
  return { name: "assignee", label: "Assigned operator", options, optionLabels: labels, value: current ? String(current) : "" };
}

function detailActions(kind: DetailKind, id: string, data: RecordData, operators: OperatorOption[]): Action[] {
  const reason = (label: string, run: (note: string) => Promise<unknown>, max = 300): Action => ({ label, fields: [{ ...note, maxLength: max }], confirm: `${label} for this record?`, run: (v) => run(v.note) });
  const actions: Action[] = [];
  const status = str(data.status);

  if (kind === "user" || kind === "brand-verification") {
    if (data.role !== "admin") actions.push(data.suspended
      ? { label: "Restore account", confirm: "Restore this account?", run: () => adminApi.restoreUser(id) }
      : { label: "Suspend account", confirm: "Apply this account suspension?", fields: [{ ...note, maxLength: 500 }, { name: "scopes", label: "What to block", type: "checkboxes", options: ["access", "funding", "earning"], optionLabels: { access: "Sign-in (whole account)", funding: "Funding campaigns", earning: "Earning and withdrawals" }, value: "access" }, { name: "days", label: "Duration in days (blank for indefinite)", type: "number", min: 1, max: 365, optional: true }], run: (v) => adminApi.suspendUser(id, { reason: v.note, scopes: v.scopes.split(","), duration_days: v.days ? Number(v.days) : null }) });
    if (data.role === "organisation") actions.push({ label: "Set business verification", confirm: "Save this business verification decision?", fields: [{ name: "verified", label: "Decision", options: ["verified", "not_verified"], optionLabels: { verified: "Verified business", not_verified: "Not verified" } }, { name: "legal_name", label: "Registered legal name", optional: true, maxLength: 160 }], run: (v) => adminApi.verifyBusiness(id, { verified: v.verified === "verified", ...(v.legal_name ? { legal_name: v.legal_name } : {}) }) });
  }

  if (kind === "campaign") {
    if (status === "active") actions.push(reason("Emergency pause", (value) => adminApi.emergencyPause(id, value), 500));
    if (status !== "closed") actions.push(reason("Emergency close", (value) => adminApi.emergencyClose(id, value), 500));
  }

  if (kind === "submission" || kind === "risk") {
    if (["needs_review", "appealed"].includes(str(data.verification_status))) {
      actions.push(reason("Approve submission", (value) => adminApi.approveSubmission(id, value), 500));
      actions.push(reason("Request correction", (value) => adminApi.requestSubmissionCorrection(id, value), 500));
    }
    if (data.admin_trust_override !== true) actions.push(reason("Clear trust flag", (value) => adminApi.clearTrustFlag(id, value), 1000));
    if (data.admin_trust_override !== false) actions.push(reason("Confirm fraud", (value) => adminApi.confirmTrustFraud(id, value), 1000));
    actions.push(data.hold_active
      ? { label: "Release earnings hold", confirm: "Release this earnings hold?", run: () => adminApi.releaseEarningsHold(id) }
      : reason("Hold earnings", (value) => adminApi.holdEarnings(id, value), 500));
    actions.push({ label: "Record trust review", fields: [{ name: "outcome", label: "Outcome", options: ["legitimate", "fraudulent", "inconclusive"] }, { name: "source", label: "Where this review came from", options: ["flagged_queue", "random_audit"], optionLabels: { flagged_queue: "Flagged queue", random_audit: "Random audit" }, value: data.flagged ? "flagged_queue" : "random_audit" }, { ...note, label: "Notes", optional: true, minLength: undefined, maxLength: 1000 }], run: (v) => adminApi.submitTrustReview(id, { outcome: v.outcome, source: v.source, notes: v.note || null }) });
  }

  if (kind === "support") actions.push(
    { label: "Send reply", fields: [{ ...note, label: "Reply to customer", minLength: 1, maxLength: 5000 }], run: (v) => adminApi.operatorReply(id, { body: v.note }) },
    { label: "Add internal note", fields: [{ ...note, label: "Note (only operators see this)", minLength: 1, maxLength: 5000 }], run: (v) => adminApi.addTicketNote(id, v.note) },
    { label: "Update ticket", fields: [{ name: "status", label: "Status", options: ["open", "closed"], value: status }, { name: "priority", label: "Priority", options: ["low", "normal", "high", "urgent"], value: str(data.priority) }, { name: "category", label: "Category", value: data.category ? str(data.category) : "", maxLength: 60, optional: true }, assigneeField(operators, data.assignee_id)], run: (v) => adminApi.updateTicket(id, { status: v.status, priority: v.priority, ...(v.category ? { category: v.category } : {}), assignee_id: v.assignee || null }) },
  );

  if (kind === "dispute") {
    if (status === "open" || status === "awaiting_customer") actions.push(
      { label: "Update dispute", fields: [{ name: "status", label: "Status", options: ["open", "awaiting_customer"], optionLabels: { open: "Open", awaiting_customer: "Waiting on customer" }, value: status }, assigneeField(operators, data.assignee_id)], run: (v) => adminApi.updateDispute(id, { status: v.status, assignee_id: v.assignee || null }) },
      { label: "Resolve dispute", fields: [{ name: "resolution", label: "Resolution", options: ["upheld", "denied", "partial"] }, { ...note, label: "Decision note (shown to the customer)", minLength: 1, maxLength: 2000 }], confirm: "Record this resolution? It doesn't move money by itself — take any refund or payout action separately.", run: (v) => adminApi.resolveDispute(id, { resolution: v.resolution, note: v.note }) },
    );
    if (status === "resolved") actions.push({ label: "Reopen dispute", confirm: "Reopen this dispute? A new resolution deadline starts now.", run: () => adminApi.reopenDispute(id) });
  }

  if (kind === "report" && status === "open") actions.push({ label: "Resolve report", fields: [{ name: "resolution", label: "Resolution", options: ["no_action", "content_restricted", "campaign_paused", "account_sanctioned", "escalated"] }, { ...note, label: "Decision note", minLength: 1, maxLength: 2000 }], confirm: "Resolve this report?", run: (v) => adminApi.resolveReport(id, { resolution: v.resolution, note: v.note }) });

  const payoutRecord = kind === "payout" || (kind === "ledger" && data.kind === "payout");
  if (payoutRecord && (status === "pending" || status === "processing")) actions.push(
    { label: "Reconcile with provider", run: () => adminApi.reconcilePayout(id) },
    { label: "Retry payout", confirm: "Retry this payout through its provider?", run: () => adminApi.retryPayout(id) },
    reason("Mark payout failed", (value) => adminApi.failPayout(id, value)),
  );

  if (kind === "ledger" && data.kind === "funding" && (status === "awaiting_payment" || status === "awaiting_confirmation")) actions.push({ label: "Confirm funds received", confirm: "Confirm this payment actually arrived? The campaign can go live after this.", fields: [{ name: "amount", label: "Amount received (NGN)", type: "number", min: 0.01, value: String(data.amount ?? "") }, note], run: (v) => adminApi.confirmFunding(id, { amount_received: Number(v.amount), note: v.note }) });

  return actions;
}

const backTo: Partial<Record<DetailKind, string>> = { user: "/admin/users", "brand-verification": "/admin/brands/verifications", "creator-verification": "/admin/creators/verifications", campaign: "/admin/campaigns", submission: "/admin/submissions", risk: "/admin/risk", support: "/admin/support", dispute: "/admin/disputes", payout: "/admin/payouts", refund: "/admin/refunds", ledger: "/admin/ledger", earning: "/admin/earnings", report: "/admin/reports", audit: "/admin/audit" };
const readOnlyNote: Partial<Record<DetailKind, string>> = {
  refund: "Refunds are processed automatically. There's no admin action to release or retry one.",
  "brand-verification": "The current verification decision isn't returned with the account. Saving a decision below replaces it.",
};

export function AdminDetailScreen({ kind, id }: { kind: DetailKind; id: string }) {
  const state = useRemote(useCallback(() => detailLoad(kind, id), [kind, id]));
  const [operators, setOperators] = useState<OperatorOption[]>([]);
  const [operatorsError, setOperatorsError] = useState("");
  useEffect(() => {
    if (kind !== "support" && kind !== "dispute") return;
    adminApi.listOperators()
      .then((rows) => {
        setOperators(rows.filter((o) => !o.suspended));
        setOperatorsError("");
      })
      .catch((err) => setOperatorsError(errorMessage(err, "Could not load the operator list.")));
  }, [kind]);
  const actions = state.data != null ? detailActions(kind, id, record(state.data), operators) : [];
  return <div className="admin-page"><AdminHeading back={backTo[kind] ?? "/admin"} title={`${titleCase(kind)} record`} copy={id} action={<AdminButton onClick={state.refresh}>Refresh</AdminButton>} />{operatorsError && <p className="admin-live-notice" role="alert">{operatorsError} Assignment controls are unavailable until it reconnects.</p>}<RemoteState {...state} retry={state.refresh}>{kind === "creator-verification" ? <p className="admin-live-notice">The backend does not provide identity evidence or an admin identity decision endpoint.</p> : state.data != null && <div className="admin-live-detail"><section className="admin-docket"><Fields data={state.data} />{readOnlyNote[kind] && <p className="admin-live-notice">{readOnlyNote[kind]}</p>}{kind === "earning" && <Link href={`/admin/submissions/${record(state.data).submission_id}`}>Open submission and earnings controls</Link>}</section><aside>{actions.length ? actions.map((action) => <ActionForm key={action.label} action={action} done={state.refresh} />) : <p className="admin-live-notice">No actions available for this record in its current state.</p>}</aside></div>}</RemoteState></div>;
}

export function AdminLedgerScreen() {
  const [kind, setKind] = useState(""), [offset, setOffset] = useState(0);
  const state = useRemote(useCallback(() => adminApi.unifiedLedger({ kind: kind || undefined, limit: pageSize, offset }), [kind, offset]));
  return <div className="admin-page"><AdminHeading title="Finance ledger" copy="Funding, refunds and payouts recorded by the backend." /><div className="admin-live-filters"><label>Entry type<select value={kind} onChange={(e) => { setKind(e.target.value); setOffset(0); }}><option value="">All entries</option>{["funding", "refund", "payout"].map((v) => <option key={v}>{v}</option>)}</select></label></div><ActionForm action={{ label: "Export ledger CSV", run: async () => download(await adminApi.exportLedger(kind || undefined), "ledger.csv") }} /><RemoteState {...state} retry={state.refresh}><div className="admin-live-table"><table><thead><tr><th>Reference</th><th>Type</th><th>Amount</th><th>Status</th><th>Provider</th></tr></thead><tbody>{state.data?.map((row) => <tr key={row.id}><td><Link href={`/admin/ledger/${row.id}`}>{row.reference}</Link></td><td>{row.kind}</td><td>{money(row.amount)}</td><td>{row.status}</td><td>{row.provider}</td></tr>)}</tbody></table>{!state.data?.length && <p>No ledger entries found.</p>}</div><div className="admin-live-pagination"><button disabled={!offset} onClick={() => setOffset(offset - pageSize)}>Previous</button><span>Page {offset / pageSize + 1}</span><button disabled={(state.data?.length ?? 0) < pageSize} onClick={() => setOffset(offset + pageSize)}>Next</button></div></RemoteState></div>;
}

export function AdminReconciliationScreen() {
  const state = useRemote(useCallback(() => adminApi.listJobs(), []));
  return <div className="admin-page"><AdminHeading title="Reconciliation and jobs" copy="Run supported backend jobs. Inspect individual payouts to reconcile their provider state." /><nav className="admin-live-links"><Link href="/admin/payouts">Payouts</Link><Link href="/admin/funding">Confirm funding</Link><Link href="/admin/ledger">Ledger</Link><Link href="/admin/providers">Provider configuration</Link></nav><div className="admin-live-action-grid"><ActionForm action={{ label: "Run earnings settlement", confirm: "Run earnings settlement now?", run: adminApi.runSettlement }} /><ActionForm action={{ label: "Sweep campaigns", confirm: "Run the campaign sweep now?", run: adminApi.runSweep }} /></div><RemoteState {...state} retry={state.refresh}><div className="admin-live-action-grid">{state.data?.map((job) => <section key={job.name}><p>Scheduled interval: {job.interval_seconds} seconds</p><ActionForm action={{ label: `Run ${job.name}`, confirm: `Run ${job.name} now?`, run: async () => { await adminApi.runJob(job.name); } }} /></section>)}</div>{!state.data?.length && <p>No jobs registered.</p>}</RemoteState></div>;
}

export function AdminOperatorsScreen() {
  const state = useRemote(useCallback(() => adminApi.listOperators(), []));
  return <div className="admin-page"><AdminHeading title="Operators" copy="Administrator accounts and their saved permission labels." action={<Link className="admin-button admin-button--lime" href="/admin/operators/invite">Invite operator</Link>} /><p className="admin-live-notice">The backend currently grants admin-role access to these operations. Saved permission labels are not enforced per route.</p><RemoteState {...state} retry={state.refresh}><div className="admin-live-action-grid">{state.data?.map((operator) => <section className="admin-docket" key={operator.id}><h2>{operator.full_name}</h2><p>{operator.email}</p><AdminStatus tone={operator.suspended ? "red" : "lime"}>{operator.suspended ? "Suspended" : "Active"}</AdminStatus><Fields data={{ id: operator.id, permissions: operator.permissions, last_active_at: operator.last_active_at, created_at: operator.created_at }} /><ActionForm action={{ label: "Save permission labels", fields: [{ name: "permissions", label: "Comma-separated permissions (blank means full legacy access)", optional: true, value: operator.permissions.join(", ") }], run: (v) => adminApi.updateOperator(operator.id, { permissions: v.permissions.split(",").map((s) => s.trim()).filter(Boolean) }) }} done={state.refresh} /><ActionForm action={{ label: operator.suspended ? "Restore operator" : "Suspend operator", confirm: "Change this operator’s access?", run: () => operator.suspended ? adminApi.restoreOperator(operator.id) : adminApi.suspendOperator(operator.id) }} done={state.refresh} /></section>)}</div>{!state.data?.length && <p>No operators found.</p>}</RemoteState></div>;
}
export function AdminInviteOperatorScreen() {
  const [result, setResult] = useState<{ email: string; expires_at: string } | null>(null);
  return <div className="admin-page"><AdminHeading title="Invite an operator" back="/admin/operators" copy="Invitations grant administrator access. Permission labels are recorded but not enforced per route." /><ActionForm action={{ label: "Create invitation", fields: [{ name: "email", label: "Email", type: "email" }, { name: "permissions", label: "Permission labels, comma-separated (optional)", optional: true }], run: async (v) => { const created = await adminApi.inviteOperator({ email: v.email, permissions: v.permissions.split(",").map((s) => s.trim()).filter(Boolean) }); setResult(created); } }} />{result && <section className="admin-live-notice" role="status"><h2>Invitation created</h2><p>{result.email} · expires {new Date(result.expires_at).toLocaleString()}</p><p>The backend handles delivery to the operator’s email.</p></section>}</div>;
}
export function AdminRolesScreen() { return <AdminOperatorsScreen />; }
export function AdminAuditScreen() {
  const [kind, setKind] = useState(""), [query, setQuery] = useState("");
  const state = useRemote(useCallback(() => adminApi.readAudit({ kind: kind || undefined, limit: 500 }), [kind]));
  return <div className="admin-page"><AdminHeading title="Audit log" copy="Latest 500 matching events recorded by the backend." /><form className="admin-live-filters" onSubmit={(e) => { e.preventDefault(); setKind(query.trim()); }}><label>Action prefix<input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="e.g. admin." /></label><button type="submit">Filter</button></form><ActionForm action={{ label: "Export audit CSV", run: async () => download(await adminApi.exportAudit(kind || undefined), "audit.csv") }} /><RemoteState {...state} retry={state.refresh}><section className="admin-audit-stream">{state.data?.map((event) => <article key={event.id}><time>{new Date(event.created_at).toLocaleString()}</time><span><i /></span><p><Link href={`/admin/audit/${event.id}`}><strong>{titleCase(event.kind)}</strong></Link><small>{event.actor_id ?? "System"} · {event.subject_id ?? event.campaign_id ?? event.submission_id ?? "—"}</small></p><span>{event.amount == null ? "—" : money(event.amount)}</span></article>)}</section>{!state.data?.length && <p>No audit events found.</p>}</RemoteState></div>;
}

export function AdminCommandCentreScreen() {
  const overview = useRemote(useCallback(() => adminApi.overview(), []));
  const ops = useRemote(useCallback(() => adminApi.opsSnapshot(), []));
  const [feed, setFeed] = useState<OpsSocketState>("connecting");
  const setOps = ops.setData;
  useEffect(() => openOpsSocket({ onState: setFeed, onMessage: (message) => { if (message.type === "snapshot") setOps((previous) => previous ? { ...previous, [message.topic]: message.data } : previous); } }), [setOps]);
  const data = overview.data;
  const feedLabel = feed === "live" ? "Live" : feed === "unauthorized" ? "Live feed unavailable" : feed === "reconnecting" ? "Reconnecting…" : "Connecting…";
  return <div className="admin-page"><AdminHeading title="Operations, right now" copy={new Date().toLocaleDateString()} action={<><AdminStatus tone={feed === "live" ? "lime" : feed === "unauthorized" ? "red" : "gold"}>{feedLabel}</AdminStatus><AdminButton onClick={() => { overview.refresh(); ops.refresh(); }}>Refresh</AdminButton></>} /><RemoteState {...overview} retry={overview.refresh}>{data && <><section className="admin-command-pulse">{[["Creator liability", money(data.creator_liability), "earnings"], ["Submissions needing review", data.submissions_needing_review, "submissions"], ["Open appeals", data.open_appeals, "submissions"], ["Blocked earning accounts", data.blocked_earning_accounts, "risk"], ["Funding awaiting confirmation", data.funding_awaiting_confirmation, "funding"]].map(([label, value, path]) => <Link key={str(label)} href={`/admin/${path}`}><small>{label}</small><strong>{value}</strong><span>Open queue</span></Link>)}</section><div className="admin-live-action-grid">{[["Users", data.users], ["Campaigns", data.campaigns], ["Payouts", data.payouts]].map(([title, values]) => <section className="admin-docket" key={str(title)}><h2>{str(title)}</h2><Fields data={values} /></section>)}</div></>}</RemoteState><RemoteState {...ops} retry={ops.refresh}>{ops.data && <section className="admin-live-action-grid">{(["system", "webhooks", "social", "notifications"] as const).map((topic) => <Link className="admin-docket" href={`/admin/${topic === "social" ? "social-connections" : topic}`} key={topic}><h2>{titleCase(topic)}</h2><p>{titleCase(ops.data![topic].status)}</p><small>Updated {new Date(ops.data![topic].generated_at).toLocaleTimeString()}</small></Link>)}</section>}</RemoteState><AdminReviewIndexScreen embedded /></div>;
}
const tools = [["users", "Customers"], ["campaigns", "Campaigns"], ["submissions", "Submissions"], ["flagged", "Flagged submissions"], ["random-audits", "Random audits"], ["support", "Support"], ["disputes", "Disputes"], ["reports", "Reports"], ["funding", "Funding"], ["earnings", "Earnings"], ["payouts", "Payouts"], ["refunds", "Refunds"], ["ledger", "Ledger"], ["reconciliation", "Jobs and reconciliation"], ["risk", "Blocked earnings"], ["trust", "Trust rules"], ["providers", "Provider configuration"], ["operators", "Operators"], ["audit", "Audit"], ["system", "System health"], ["webhooks", "Webhooks"], ["social-connections", "Social providers"], ["notifications", "Notifications"]];
export function AdminReviewIndexScreen({ embedded = false }: { embedded?: boolean }) { return <section className={embedded ? "" : "admin-page"}>{!embedded && <AdminHeading title="Operations directory" copy="Open a live queue, then select a record to inspect it." />}<nav className="admin-live-links">{tools.map(([path, label]) => <Link key={path} href={`/admin/${path}`}>{label}</Link>)}</nav></section>; }
export function AdminReferenceScreen({ kind }: { kind: "trust" | "providers" }) {
  const state = useRemote(useCallback(() => kind === "trust" ? adminApi.trustRules() : adminApi.providerHealth(), [kind]));
  return <div className="admin-page"><AdminHeading title={kind === "trust" ? "Trust rules" : "Provider configuration"} /><RemoteState {...state} retry={state.refresh}><section className="admin-docket"><Fields data={state.data} /></section></RemoteState></div>;
}
