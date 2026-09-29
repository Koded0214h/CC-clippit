"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ProductIcon } from "@/components/ui/ProductIcon";
import { ClippitLoader } from "@/components/ui/ClippitLoader";
import { ClippitEmptyState } from "@/components/ui/ClippitEmptyState";
import { adminApi, type DeliveryCard, type DeliveryFeed, type DeliveryStatus, type OpsStatus, type SystemHealth } from "@/lib/api/admin";
import { openOpsSocket, type OpsSocketState, type OpsTopic } from "@/lib/api/opsSocket";
import { AdminHeading, AdminStatus, type Tone } from "./AdminScreens";

/**
 * One topic, kept live: REST for the first paint, then the /admin/ws socket pushes fresh
 * snapshots. If the socket can't authenticate or is down, it falls back to polling REST.
 */
function useTopic<T>(topic: OpsTopic, load: () => Promise<T>) {
  const [data, setData] = useState<T | null>(null);
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [socket, setSocket] = useState<OpsSocketState>("connecting");
  const [lastEvent, setLastEvent] = useState<number | null>(null);

  useEffect(() => {
    let alive = true;
    const fetchOnce = () => load().then((value) => { if (alive) { setData(value); setFailed(false); } }).catch(() => { if (alive) setFailed(true); }).finally(() => { if (alive) setLoading(false); });
    fetchOnce();
    const close = openOpsSocket({
      topics: [topic],
      onState: (state) => alive && setSocket(state),
      onMessage: (message) => {
        if (!alive) return;
        if (message.type === "snapshot" && message.topic === topic) { setData(message.data as T); setFailed(false); setLoading(false); }
        // A live webhook lands between snapshots: re-read so the counts and log update immediately.
        if (message.type === "event" && topic === "webhooks") { setLastEvent(message.event.ts); fetchOnce(); }
      },
    });
    return () => { alive = false; close(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [topic]);

  // Poll only while the socket isn't delivering.
  useEffect(() => {
    if (socket === "live") return;
    const timer = setInterval(() => { if (!document.hidden) load().then(setData).catch(() => undefined); }, 15000);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [socket]);

  return { data, failed, loading, socket, lastEvent };
}

const clock = (ms: number | null) => (ms == null ? "" : new Date(ms).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }));
const bars = (values: number[]) => { const max = Math.max(...values, 1); return values.map((v) => Math.max(6, Math.round((v / max) * 100))); };
const uptime = (seconds: number) => { const d = Math.floor(seconds / 86400), h = Math.floor((seconds % 86400) / 3600), m = Math.floor((seconds % 3600) / 60); return d ? `${d}d ${h}h` : h ? `${h}h ${m}m` : `${m}m`; };

function Unavailable({ what }: { what: string }) {
  return <div className="admin-page"><ClippitEmptyState icon="shield" tone="gold" title={`${what} is unavailable`} copy="The API didn't answer. Check that you're signed in as an operator and that the API is reachable, then reload." /></div>;
}

const liveTone = (socket: OpsSocketState): Tone => (socket === "live" ? "lime" : socket === "unauthorized" ? "red" : "gold");
const liveLabel = (socket: OpsSocketState) => (socket === "live" ? "Live" : socket === "unauthorized" ? "Polling" : "Connecting");

const serviceTone: Record<OpsStatus, Tone> = { operational: "lime", degraded: "gold", down: "red", sandbox: "blue", disabled: "paper" };
const serviceLabel: Record<OpsStatus, string> = { operational: "Operational", degraded: "Degraded", down: "Down", sandbox: "Sandbox", disabled: "Off" };

export function AdminSystemScreen() {
  const { data, failed, loading, socket } = useTopic<SystemHealth>("system", adminApi.systemHealth);
  if (loading) return <div className="admin-page"><ClippitLoader contained tone="ink" label="Checking the services" note="Pinging the database and reading live traffic." /></div>;
  if (!data) return failed ? <Unavailable what="System health" /> : null;

  const ms = (v: number | null) => (v == null ? "—" : `${Math.round(v)} ms`);
  const trafficBars = bars(data.series.map((p) => p.ok + p.client_err + p.server_err));
  return <div className="admin-page">
    <AdminHeading eyebrow="Runtime controls" title="System health" copy={`Up ${uptime(data.uptime_seconds)} · ${data.environment}`}
      action={<span style={{ display: "flex", gap: 8 }}><AdminStatus tone={liveTone(socket)}>{liveLabel(socket)}</AdminStatus><AdminStatus tone={data.status === "operational" ? "lime" : data.status === "degraded" ? "gold" : "red"}>{data.status === "operational" ? "All systems operational" : data.status === "degraded" ? "Degraded" : "Service down"}</AdminStatus></span>} />
    <section className="admin-system-grid">{data.services.map((service) => {
      const chart = service.trend.length > 1 ? bars(service.trend) : null;
      return <article key={service.key}>
        <header><span><i /></span><AdminStatus tone={serviceTone[service.status]}>{serviceLabel[service.status]}</AdminStatus></header>
        <h2>{service.name}</h2>
        <p>{service.detail}</p>
        <dl>
          <div><dt>{service.headline.label}</dt><dd>{service.headline.display}</dd></div>
          <div><dt>30-day availability</dt><dd>{service.availability_30d == null ? "Collecting" : `${service.availability_30d}%`}</dd></div>
        </dl>
        {chart && <div aria-hidden>{chart.map((height, i) => <i key={i} style={{ height: `${height}%` }} />)}</div>}
      </article>;
    })}</section>
    <section className="admin-delivery-detail">
      <header><div><h2>Traffic and latency</h2><p>Last 30 minutes · counted since the API last restarted</p></div><strong>{data.requests.toLocaleString()}</strong></header>
      <div className="admin-signal-chart" aria-hidden>{trafficBars.map((height, i) => <i key={i} style={{ height: `${height}%` }} />)}</div>
      <footer><span><i />p50 {ms(data.latency.p50)}</span><span><i />p95 {ms(data.latency.p95)} · p99 {ms(data.latency.p99)}</span><span>{data.error_rate}% server errors · {data.throughput_rpm} req/min · {data.log_counts.error} errors, {data.log_counts.warn} warnings logged</span></footer>
    </section>
  </div>;
}

const statusTone: Record<DeliveryStatus, Tone> = { healthy: "lime", attention: "gold", failing: "red", quiet: "paper", unconfigured: "paper" };
const statusLabel: Record<DeliveryStatus, string> = { healthy: "Healthy", attention: "Attention", failing: "Failing", quiet: "Quiet", unconfigured: "Not set up" };
const resultWarn = (result: string) => ["failed", "rejected", "retried", "problem"].includes(result);

const kinds = {
  social: { topic: "social" as const, load: () => adminApi.socialDelivery(), icon: "link" as const, title: "Social provider health", copy: "Platform connections, permissions and view-reading freshness." },
  webhooks: { topic: "webhooks" as const, load: () => adminApi.webhookDelivery(), icon: "spark" as const, title: "Webhook delivery", copy: "Provider events, rejected signatures and failures." },
  notifications: { topic: "notifications" as const, load: () => adminApi.notificationDelivery(), icon: "bell" as const, title: "Notification delivery", copy: "Email, in-app and push delivery across customer journeys." },
};

export function AdminDeliveryScreen({ kind }: { kind: keyof typeof kinds }) {
  const cfg = kinds[kind];
  const { data, failed, loading, socket, lastEvent } = useTopic<DeliveryFeed>(cfg.topic, cfg.load);
  const [selected, setSelected] = useState(0);
  if (loading) return <div className="admin-page"><ClippitLoader contained tone="ink" label="Reading delivery state" note="Checking providers and recent events." /></div>;
  if (!data) return failed ? <Unavailable what={cfg.title} /> : null;

  const active: DeliveryCard | undefined = data.cards[selected] ?? data.cards[0];
  const buckets = active?.window?.buckets ?? [];
  const heights = bars(buckets.map((b) => b.ok + b.retried + b.failed));
  const rows = active ? (active.events.length ? active.events.map((e) => ({ time: clock(e.ts), title: e.title, sub: `${e.id} · ${e.ref}`, result: e.result, warn: resultWarn(e.result) }))
    : Object.entries(active.facts).map(([k, v]) => ({ time: "", title: k.replace(/_/g, " "), sub: "", result: v == null ? "—" : String(v), warn: false }))) : [];
  const tone = data.status === "healthy" ? "lime" : data.status === "attention" ? "gold" : "red";

  return <div className="admin-page">
    <AdminHeading eyebrow="Trust & delivery" title={cfg.title} copy={cfg.copy}
      action={<span style={{ display: "flex", gap: 8 }}><AdminStatus tone={liveTone(socket)}>{liveLabel(socket)}</AdminStatus><AdminStatus tone={tone}>{data.status === "healthy" ? "Monitoring" : data.status === "attention" ? "Needs attention" : "Failing"}</AdminStatus></span>} />
    <section className="admin-provider-grid">{data.cards.map((card, index) => <button type="button" key={card.key} className={selected === index ? "is-selected" : ""} onClick={() => setSelected(index)}>
      <span><ProductIcon name={cfg.icon} /></span>
      <p><strong>{card.name}</strong><small>{card.note}</small></p>
      <b>{card.success_rate == null ? card.headline.display : `${card.success_rate}%`}</b>
      <AdminStatus tone={statusTone[card.status]}>{statusLabel[card.status]}</AdminStatus>
    </button>)}</section>
    {active && <section className="admin-delivery-detail">
      <header><div><h2>{active.name}</h2><p>{data.scope}{lastEvent ? ` · last event ${clock(lastEvent)}` : ""}</p></div><strong>{active.headline.display}</strong></header>
      {buckets.length > 0 && <div className="admin-signal-chart" aria-hidden>{heights.map((height, i) => <i key={i} style={{ height: `${height}%`, background: buckets[i].failed ? "var(--admin-gold)" : undefined }} />)}</div>}
      <footer>{buckets.length > 0 && <><span><i />Successful</span><span><i />Failed</span></>}<Link href="/admin/audit">View related audit events<ProductIcon name="arrow" /></Link></footer>
    </section>}
    <section className="admin-delivery-log">{rows.length === 0
      ? <article><time /><span><i /></span><p><strong>Nothing to show yet</strong><small>No events since the API last restarted.</small></p><b /></article>
      : rows.map((item, i) => <article key={`${item.title}-${i}`}><time>{item.time}</time><span><i className={item.warn ? "is-warn" : ""} /></span><p><strong>{item.title}</strong><small>{item.sub}</small></p><b>{item.result}</b></article>)}</section>
  </div>;
}
