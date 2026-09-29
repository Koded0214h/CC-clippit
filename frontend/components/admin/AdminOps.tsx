"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ProductIcon } from "@/components/ui/ProductIcon";
import { ClippitLoader } from "@/components/ui/ClippitLoader";
import { ClippitEmptyState } from "@/components/ui/ClippitEmptyState";
import {
  adminApi,
  type NotificationDelivery,
  type SocialDelivery,
  type SystemHealth,
  type SystemService,
  type WebhookDelivery,
} from "@/lib/api/admin";
import { AdminHeading, AdminStatus, relativeTime, type Tone } from "./AdminScreens";

/** Loads once, then refreshes quietly so the screen stays live without flashing the loader. */
function useLive<T>(load: () => Promise<T>, everyMs = 15000) {
  const [data, setData] = useState<T | null>(null);
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let alive = true;
    const run = () => load().then((value) => { if (alive) { setData(value); setFailed(false); } }).catch(() => { if (alive) setFailed(true); }).finally(() => { if (alive) setLoading(false); });
    run();
    const timer = setInterval(() => { if (!document.hidden) run(); }, everyMs);
    return () => { alive = false; clearInterval(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return { data, failed, loading };
}

function uptime(seconds: number): string {
  const d = Math.floor(seconds / 86400), h = Math.floor((seconds % 86400) / 3600), m = Math.floor((seconds % 3600) / 60);
  return d ? `${d}d ${h}h` : h ? `${h}h ${m}m` : `${m}m`;
}
const clock = (ms: number) => new Date(ms).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
const bars = (values: number[]) => { const max = Math.max(...values, 1); return values.map((v) => Math.max(6, Math.round((v / max) * 100))); };

function Unavailable({ what }: { what: string }) {
  return <div className="admin-page"><ClippitEmptyState icon="shield" tone="gold" title={`${what} is unavailable`} copy="The API didn't answer. Check that you're signed in as an operator and that the API is reachable, then reload." /></div>;
}

const serviceTone: Record<SystemService["status"], Tone> = { operational: "lime", degraded: "gold", down: "red", sandbox: "blue", disabled: "paper" };
const serviceLabel: Record<SystemService["status"], string> = { operational: "Operational", degraded: "Degraded", down: "Down", sandbox: "Sandbox", disabled: "Off" };

export function AdminSystemScreen() {
  const { data, failed, loading } = useLive<SystemHealth>(adminApi.systemHealth);
  if (loading) return <div className="admin-page"><ClippitLoader contained tone="ink" label="Checking the services" note="Pinging the database and reading live traffic." /></div>;
  if (!data) return failed ? <Unavailable what="System health" /> : null;

  const worst = data.services.some((s) => s.status === "down") ? "down" : data.services.some((s) => s.status === "degraded") ? "degraded" : "operational";
  const trafficBars = bars(data.series.map((p) => p.ok + p.client_err + p.server_err));
  const dbBars = bars(data.db_history.map((p) => p.ms ?? 0));
  const ms = (v: number | null) => (v == null ? "—" : `${Math.round(v)} ms`);

  return <div className="admin-page">
    <AdminHeading eyebrow="Runtime controls" title="System health" copy={`Live from the API process · up ${uptime(data.uptime_seconds)} · ${data.environment}`}
      action={<AdminStatus tone={worst === "operational" ? "lime" : worst === "degraded" ? "gold" : "red"}>{worst === "operational" ? "All systems operational" : worst === "degraded" ? "Degraded" : "Service down"}</AdminStatus>} />
    <section className="admin-system-grid">{data.services.map((service) => {
      const chart = service.name === "API" ? trafficBars : service.name === "Database" ? dbBars : null;
      return <article key={service.name}>
        <header><span><i /></span><AdminStatus tone={serviceTone[service.status]}>{serviceLabel[service.status]}</AdminStatus></header>
        <h2>{service.name}</h2>
        <dl><div><dt>Now</dt><dd>{service.metric}</dd></div><div><dt>Detail</dt><dd>{service.detail}</dd></div></dl>
        {chart && chart.length > 1 && <div aria-hidden>{chart.map((height, i) => <i key={i} style={{ height: `${height}%` }} />)}</div>}
      </article>;
    })}</section>
    <section className="admin-delivery-detail">
      <header><div><h2>Traffic and latency</h2><p>Last 30 minutes · counted since the API last restarted</p></div><strong>{data.requests.toLocaleString()}</strong></header>
      <div className="admin-signal-chart" aria-hidden>{trafficBars.map((height, i) => <i key={i} style={{ height: `${height}%` }} />)}</div>
      <footer><span><i />p50 {ms(data.latency.p50)}</span><span><i />p95 {ms(data.latency.p95)} · p99 {ms(data.latency.p99)}</span><span>{data.error_rate}% server errors · {data.throughput_rpm} req/min · {data.log_counts.error} errors, {data.log_counts.warn} warnings logged</span></footer>
    </section>
  </div>;
}

type Card = { key: string; title: string; note: string; big: string; tone: Tone; label: string };

export function AdminDeliveryScreen({ kind }: { kind: "social" | "webhooks" | "notifications" }) {
  const loader = kind === "social" ? adminApi.socialDelivery : kind === "webhooks" ? adminApi.webhookDelivery : adminApi.notificationDelivery;
  const { data, failed, loading } = useLive<SocialDelivery | WebhookDelivery | NotificationDelivery>(loader);
  const [selected, setSelected] = useState(0);
  const titles = { social: ["Social provider health", "Platform credentials, connected accounts and expired tokens."], webhooks: ["Webhook delivery", "Provider events, rejected signatures and failures."], notifications: ["Notification delivery", "Email, in-app and push delivery across customer journeys."] } as const;
  if (loading) return <div className="admin-page"><ClippitLoader contained tone="ink" label="Reading delivery state" note="Checking providers and recent events." /></div>;
  if (!data) return failed ? <Unavailable what={titles[kind][0]} /> : null;

  let cards: Card[] = [];
  let chart: { heights: number[]; warn: boolean[]; caption: string } | null = null;
  let log: Array<{ time: string; title: string; sub: string; result: string; warn: boolean }> = [];
  let scope = "Live";

  if (kind === "webhooks") {
    const d = data as WebhookDelivery;
    scope = `Since API restart · ${relativeTime(new Date(d.since).toISOString())}`;
    cards = d.groups.map((g) => ({
      key: g.name, title: g.name, note: g.events ? `${g.events} events · ${g.rejected} rejected · ${g.failed} failed` : g.note,
      big: g.success_rate == null ? "—" : `${g.success_rate}%`, tone: g.events === 0 ? "paper" : g.failed ? "red" : g.rejected ? "gold" : "lime",
      label: g.events === 0 ? "Quiet" : g.failed ? "Failing" : g.rejected ? "Attention" : "Healthy",
    }));
    chart = { heights: bars(d.buckets.map((b) => b.ok + b.err)), warn: d.buckets.map((b) => b.err > 0), caption: "Requests to the API, per minute · last 60 min" };
    log = d.recent.map((e) => ({ time: clock(e.ts), title: `${e.method} ${e.path}`, sub: `${e.duration_ms} ms`, result: `${e.status}`, warn: e.status >= 400 }));
  } else if (kind === "social") {
    const d = data as SocialDelivery;
    cards = d.platforms.map((p) => ({
      key: p.name, title: p.name.charAt(0).toUpperCase() + p.name.slice(1),
      note: p.configured ? `${p.connected} connected · ${p.expired} expired` : "No credentials configured",
      big: String(p.connected), tone: p.status === "healthy" ? "lime" : p.status === "attention" ? "gold" : "paper",
      label: p.status === "healthy" ? "Healthy" : p.status === "attention" ? "Attention" : "Not set up",
    }));
    const p = d.platforms[selected] ?? d.platforms[0];
    if (p) log = [
      { time: "", title: "Credentials", sub: p.configured ? "Client id and secret are set" : "Set the platform's client id and secret on the server", result: p.configured ? "Set" : "Missing", warn: !p.configured },
      { time: "", title: "Connected accounts", sub: `${p.connected} creator${p.connected === 1 ? "" : "s"} linked`, result: String(p.connected), warn: false },
      { time: "", title: "Expired tokens", sub: "Expired with no refresh token — the creator must reconnect", result: String(p.expired), warn: p.expired > 0 },
      { time: "", title: "Last connection change", sub: p.last_update ? relativeTime(p.last_update) : "Nothing connected yet", result: "", warn: false },
    ];
  } else {
    const d = data as NotificationDelivery;
    cards = [
      { key: "email", title: "Email", note: `Backend: ${d.email.backend}`, big: String(d.email.problems.length), tone: d.email.status === "healthy" ? "lime" : "gold", label: d.email.status === "healthy" ? "Healthy" : "Attention" },
      { key: "inapp", title: "In-app", note: `${d.in_app.unread_24h} unread of ${d.in_app.created_24h} (24 h)`, big: String(d.in_app.created_24h), tone: "lime", label: "Healthy" },
      { key: "push", title: "Push", note: "Browser subscriptions", big: String(d.push.subscriptions), tone: d.push.subscriptions ? "lime" : "paper", label: d.push.subscriptions ? "Healthy" : "None yet" },
    ];
    if (selected === 0) log = d.email.problems.map((e) => ({ time: clock(e.ts), title: e.message, sub: "Email sender", result: "Problem", warn: true }));
    else if (selected === 1) { log = d.in_app.by_kind.map((k) => ({ time: "", title: k.kind, sub: "Last 24 hours", result: String(k.count), warn: false })); chart = { heights: bars(d.in_app.by_kind.map((k) => k.count)), warn: d.in_app.by_kind.map(() => false), caption: "In-app notifications by kind · last 24 h" }; }
  }
  const active = cards[selected] ?? cards[0];
  const icon = kind === "social" ? "link" : kind === "webhooks" ? "spark" : "bell";
  const overall = cards.some((c) => c.tone === "red") ? "red" : cards.some((c) => c.tone === "gold") ? "gold" : "lime";

  return <div className="admin-page">
    <AdminHeading eyebrow="Trust & delivery" title={titles[kind][0]} copy={titles[kind][1]} action={<AdminStatus tone={overall}>{overall === "lime" ? "Monitoring" : overall === "gold" ? "Needs attention" : "Failing"}</AdminStatus>} />
    <section className="admin-provider-grid">{cards.map((item, index) => <button type="button" key={item.key} className={selected === index ? "is-selected" : ""} onClick={() => setSelected(index)}><span><ProductIcon name={icon} /></span><p><strong>{item.title}</strong><small>{item.note}</small></p><b>{item.big}</b><AdminStatus tone={item.tone}>{item.label}</AdminStatus></button>)}</section>
    {active && <section className="admin-delivery-detail">
      <header><div><h2>{active.title}</h2><p>{scope}</p></div><strong>{active.big}</strong></header>
      {chart && <div className="admin-signal-chart" aria-hidden>{chart.heights.map((height, i) => <i key={i} style={{ height: `${height}%`, background: chart.warn[i] ? "var(--admin-gold)" : undefined }} />)}</div>}
      <footer>{chart && <span><i />{chart.caption}</span>}<Link href="/admin/audit">View related audit events<ProductIcon name="arrow" /></Link></footer>
    </section>}
    <section className="admin-delivery-log">{log.length === 0
      ? <article><time /><span><i /></span><p><strong>Nothing to show yet</strong><small>{kind === "webhooks" ? "No webhook has reached the API since it last restarted." : "No recent events."}</small></p><b /></article>
      : log.map((item, i) => <article key={`${item.title}-${i}`}><time>{item.time}</time><span><i className={item.warn ? "is-warn" : ""} /></span><p><strong>{item.title}</strong><small>{item.sub}</small></p><b>{item.result}</b></article>)}</section>
  </div>;
}
