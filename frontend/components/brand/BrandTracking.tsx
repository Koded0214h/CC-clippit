"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AnimatedNumber } from "@/components/ui/AnimatedNumber";
import { ClippitEmptyState } from "@/components/ui/ClippitEmptyState";
import { ClippitLoader } from "@/components/ui/ClippitLoader";
import { ProductIcon } from "@/components/ui/ProductIcon";
import {
  campaignsApi,
  type CampaignIntegrationOut,
  type CampaignOut,
  type PerformanceMetricType,
} from "@/lib/api/campaigns";
import { errorMessage } from "@/lib/api/client";

const conversionTypes = new Set<PerformanceMetricType>(["visit", "signup", "lead", "purchase"]);

const labels: Record<string, string> = {
  visit: "Visits",
  signup: "Signups",
  lead: "Leads",
  purchase: "Purchases or paid uses",
};

function formatDate(value: string | null) {
  if (!value) return "No event received";
  return new Intl.DateTimeFormat("en-NG", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function TrackingHead({
  eyebrow,
  title,
  copy,
  back,
}: {
  eyebrow: string;
  title: string;
  copy: string;
  back?: string;
}) {
  return (
    <header className="tracking-head">
      {back ? (
        <Link href={back} className="brand-back">
          <ProductIcon name="arrow" /> Back to campaign
        </Link>
      ) : null}
      <small>{eyebrow}</small>
      <h1>{title}</h1>
      <p>{copy}</p>
    </header>
  );
}

function CopyButton({ value, label = "Copy" }: { value: string; label?: string }) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  };

  return (
    <button type="button" className="tracking-copy" onClick={copy}>
      <ProductIcon name={copied ? "check" : "brief"} />
      {copied ? "Copied" : label}
    </button>
  );
}

function SignalPath() {
  const steps = [
    ["01", "Creator link", "The creator gets a campaign-specific link."],
    ["02", "Your website", "The customer arrives with a Clippit reference."],
    ["03", "Customer action", "They sign up, order or complete a paid action."],
    ["04", "Confirmed result", "Your server sends the result to Clippit."],
  ];
  return (
    <section className="tracking-signal" aria-label="Customer tracking flow">
      <header>
        <span><ProductIcon name="link" /></span>
        <div><small>Signal path</small><strong>From creator link to confirmed result</strong></div>
      </header>
      <div>
        {steps.map(([number, title, copy], index) => (
          <article key={number}>
            <i>{number}</i>
            <p><strong>{title}</strong><small>{copy}</small></p>
            {index < steps.length - 1 ? <ProductIcon name="arrow" /> : <ProductIcon name="check" />}
          </article>
        ))}
      </div>
    </section>
  );
}

export function BrandTrackingScreen() {
  const [campaigns, setCampaigns] = useState<CampaignOut[]>([]);
  const [statuses, setStatuses] = useState<Record<string, CampaignIntegrationOut>>({});
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    campaignsApi.list({ limit: 100 })
      .then(async (rows) => {
        const tracked = rows.filter((campaign) =>
          campaign.performance_metrics.some((metric) => conversionTypes.has(metric.metric_type)),
        );
        setCampaigns(tracked);
        const settled = await Promise.allSettled(
          tracked.map(async (campaign) => [campaign.id, await campaignsApi.integration(campaign.slug)] as const),
        );
        setStatuses(Object.fromEntries(settled.flatMap((result) => result.status === "fulfilled" ? [result.value] : [])));
      })
      .catch((error) => setLoadError(errorMessage(error, "We couldn't load customer tracking.")))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="brand-page"><ClippitLoader contained tone="gold" label="Loading customer tracking" /></div>;
  if (loadError) return <div className="brand-page"><ClippitEmptyState tone="danger" icon="link" title="Customer tracking is unavailable" copy={loadError} role="alert" /></div>;

  const connected = campaigns.filter((campaign) => statuses[campaign.id]?.configured).length;
  const totalEvents = campaigns.reduce((total, campaign) => total + (statuses[campaign.id]?.events_received ?? 0), 0);

  return (
    <div className="brand-page tracking-page">
      <TrackingHead
        eyebrow="Customer tracking"
        title="Track what happens after the click."
        copy="Connect signups, orders and other paid customer actions to the creator who brought them."
      />
      <SignalPath />
      <section className="tracking-summary">
        <div><small>Campaigns using tracking</small><strong><AnimatedNumber value={campaigns.length} padStart={2} /></strong></div>
        <div><small>Server connections ready</small><strong><AnimatedNumber value={connected} padStart={2} /></strong></div>
        <div><small>Tracked events received</small><strong><AnimatedNumber value={totalEvents} format="compact" /></strong></div>
        <span><ProductIcon name="shield" /> Server-confirmed actions only</span>
      </section>
      <section className="tracking-campaigns">
        <header><div><small>Campaign connections</small><h2>Choose a campaign to set up</h2></div><Link href="/brand/campaigns/new/metrics">New campaign<ProductIcon name="arrow" /></Link></header>
        {!campaigns.length ? (
          <ClippitEmptyState
            tone="gold"
            icon="link"
            title="No customer tracking campaign yet"
            copy="Choose visits, signups, leads or purchases when you create a campaign."
            action={<Link className="brand-button" href="/brand/campaigns/new/metrics">Choose campaign results<ProductIcon name="arrow" /></Link>}
          />
        ) : (
          <div>
            {campaigns.map((campaign) => {
              const status = statuses[campaign.id];
              const metrics = campaign.performance_metrics.filter((metric) => conversionTypes.has(metric.metric_type));
              return (
                <Link href={`/brand/campaigns/${campaign.slug}/integration`} key={campaign.id}>
                  <span className="tracking-campaigns__index">{String(campaigns.indexOf(campaign) + 1).padStart(2, "0")}</span>
                  <p><strong>{campaign.title}</strong><small>{status?.destination_url ?? campaign.conversion_setup?.destination_url ?? "Customer destination"}</small></p>
                  <div className="tracking-metric-tags">{metrics.map((metric) => <span key={metric.metric_type}>{labels[metric.metric_type]}</span>)}</div>
                  <b className={status?.configured ? "is-ready" : ""}><i />{status?.configured ? "Connected" : "Setup needed"}</b>
                  <ProductIcon name="arrow" />
                </Link>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}

type CodeLanguage = "node" | "python" | "curl";

function eventPayload(eventType: string, campaignId: string) {
  const purchaseFields = eventType === "purchase"
    ? `,\n    value_amount: order.total,\n    currency: "NGN"`
    : "";
  return `{
    campaign_id: "${campaignId}",
    event_type: "${eventType}",
    attribution_code: clippitRef,
    source_event_id: "YOUR_UNIQUE_EVENT_ID",
    quantity: 1${purchaseFields}
  }`;
}

function serverCode(language: CodeLanguage, eventType: string, campaignId: string, endpoint: string) {
  if (language === "python") {
    const purchase = eventType === "purchase" ? `,\n        "value_amount": order_total,\n        "currency": "NGN"` : "";
    return `import os
import requests

requests.post(
    "${endpoint}",
    headers={"X-Clippit-Secret": os.environ["CLIPPIT_CAMPAIGN_SECRET"]},
    json={
        "campaign_id": "${campaignId}",
        "event_type": "${eventType}",
        "attribution_code": clippit_ref,
        "source_event_id": "YOUR_UNIQUE_EVENT_ID",
        "quantity": 1${purchase}
    },
    timeout=10,
).raise_for_status()`;
  }
  if (language === "curl") {
    const purchase = eventType === "purchase" ? `,"value_amount":35000,"currency":"NGN"` : "";
    return `curl -X POST "${endpoint}" \\
  -H "Content-Type: application/json" \\
  -H "X-Clippit-Secret: $CLIPPIT_CAMPAIGN_SECRET" \\
  -d '{"campaign_id":"${campaignId}","event_type":"${eventType}","attribution_code":"CLIPPIT_REF","source_event_id":"YOUR_UNIQUE_EVENT_ID","quantity":1${purchase}}'`;
  }
  return `await fetch("${endpoint}", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-Clippit-Secret": process.env.CLIPPIT_CAMPAIGN_SECRET
  },
  body: JSON.stringify(${eventPayload(eventType, campaignId)})
});`;
}

export function CampaignIntegrationScreen({ slug }: { slug: string }) {
  const [campaign, setCampaign] = useState<CampaignOut | null>(null);
  const [integration, setIntegration] = useState<CampaignIntegrationOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [language, setLanguage] = useState<CodeLanguage>("node");
  const [eventType, setEventType] = useState("signup");
  const [secret, setSecret] = useState("");
  const [secretBusy, setSecretBusy] = useState(false);
  const [secretError, setSecretError] = useState("");

  const reloadIntegration = async () => {
    const next = await campaignsApi.integration(slug);
    setIntegration(next);
    return next;
  };

  useEffect(() => {
    Promise.all([campaignsApi.get(slug), campaignsApi.integration(slug)])
      .then(([campaignData, integrationData]) => {
        setCampaign(campaignData);
        setIntegration(integrationData);
        setEventType(integrationData.selected_event_types.find((type) => type !== "visit") ?? "");
      })
      .catch((error) => setLoadError(errorMessage(error, "We couldn't load this campaign connection.")))
      .finally(() => setLoading(false));
  }, [slug]);

  const browserTag = useMemo(() => integration
    ? `<script src="${integration.tracker_script_url}" data-attribution-days="${integration.attribution_window_days}" defer></script>`
    : "", [integration]);
  const captureCode = `const clippitRef = window.ClippitTracking?.getAttribution();

// Include this value in your signup, order or paid action request.
await createCustomerAction({ ...formData, clippit_ref: clippitRef });`;
  const serverEventTypes = integration?.selected_event_types.filter((type) => type !== "visit") ?? [];
  const requiresServer = serverEventTypes.length > 0;
  const confirmCode = integration && eventType
    ? serverCode(language, eventType, integration.campaign_id, integration.event_endpoint)
    : "";

  const createSecret = async () => {
    if (secretBusy) return;
    setSecretBusy(true);
    setSecretError("");
    try {
      const result = await campaignsApi.rotateIntegrationSecret(slug);
      setSecret(result.secret);
      await reloadIntegration();
    } catch (error) {
      setSecretError(errorMessage(error, "The server key could not be created."));
    } finally {
      setSecretBusy(false);
    }
  };

  if (loading) return <div className="brand-page"><ClippitLoader contained tone="gold" label="Loading tracking setup" /></div>;
  if (loadError || !campaign || !integration) return <div className="brand-page"><ClippitEmptyState tone="danger" icon="link" title="Tracking setup is unavailable" copy={loadError || "Campaign not found."} role="alert" /></div>;
  if (!integration.selected_event_types.length) return <div className="brand-page"><TrackingHead back={`/brand/campaigns/${slug}`} eyebrow="Customer tracking" title={campaign.title} copy="This campaign does not measure visits, signups, leads or purchases." /><ClippitEmptyState tone="gold" icon="link" title="Customer tracking is off" copy="Create a campaign with a customer result to use this setup." action={<Link className="brand-button" href="/brand/campaigns/new/metrics">Create another campaign<ProductIcon name="arrow" /></Link>} /></div>;

  return (
    <div className="brand-page tracking-page tracking-setup">
      <TrackingHead back={`/brand/campaigns/${slug}`} eyebrow="Campaign connection" title={campaign.title} copy={requiresServer ? "Install the browser tag once, pass the creator reference with the customer action, then confirm the result from your server." : "Visits are recorded when customers use a creator's campaign link. The browser tag keeps the reference available on your website."} />
      <section className="tracking-connection-bar">
        <div className={integration.configured || !requiresServer ? "is-live" : ""}><i /><span><small>Server key</small><strong>{requiresServer ? integration.configured ? `Ready, ending ${integration.secret_last_four}` : "Not created" : "Not needed for visits"}</strong></span></div>
        <div><ProductIcon name="link" /><span><small>Destination</small><strong>{integration.destination_url ?? "Not set"}</strong></span></div>
        <div><ProductIcon name="clock" /><span><small>Attribution</small><strong>{integration.attribution_window_days} days, first creator</strong></span></div>
        <div><ProductIcon name="check" /><span><small>Tracked events</small><strong><AnimatedNumber value={integration.events_received} /></strong></span></div>
      </section>
      <SignalPath />
      <section className="tracking-workbench">
        <aside>
          <small>Installation</small>
          <a href="#browser-tag"><b>1</b><span>Install browser tag</span></a>
          {requiresServer ? <>
            <a href="#capture-reference"><b>2</b><span>Keep the creator reference</span></a>
            <a href="#server-key"><b>3</b><span>Create server key</span></a>
            <a href="#confirm-event"><b>4</b><span>Confirm the result</span></a>
            <p><ProductIcon name="shield" /><span><strong>Keep the server key private.</strong> It belongs in your backend environment, never browser code.</span></p>
          </> : null}
        </aside>
        <div className="tracking-workbench__steps">
          <article id="browser-tag">
            <header><span>01</span><div><small>Your website</small><h2>Install the browser tag</h2><p>Add this before the closing body tag on pages where customers land, sign up or pay.</p></div></header>
            <div className="tracking-code"><div><span>HTML</span><CopyButton value={browserTag} /></div><pre><code>{browserTag}</code></pre></div>
          </article>
          {requiresServer ? <><article id="capture-reference">
            <header><span>02</span><div><small>Your website</small><h2>Keep the creator reference</h2><p>Send the reference to your own backend with the signup, order or paid action.</p></div></header>
            <div className="tracking-code"><div><span>Browser JavaScript</span><CopyButton value={captureCode} /></div><pre><code>{captureCode}</code></pre></div>
            <p className="tracking-note"><ProductIcon name="check" />The tag also fills hidden inputs named <code>clippit_ref</code> automatically.</p>
          </article>
          <article id="server-key">
            <header><span>03</span><div><small>Your backend</small><h2>Create the campaign server key</h2><p>Create it once, copy it now and save it in your backend environment.</p></div></header>
            {secret ? (
              <div className="tracking-secret" role="status"><div><ProductIcon name="shield" /><span><small>Shown once</small><strong>Save this before leaving the page</strong></span></div><code>{secret}</code><CopyButton value={`CLIPPIT_CAMPAIGN_SECRET=${secret}`} label="Copy .env line" /></div>
            ) : (
              <div className="tracking-key-action"><div><span className={integration.configured ? "is-live" : ""}><i /></span><p><strong>{integration.configured ? "A server key is active" : "No server key yet"}</strong><small>{integration.configured ? `Current key ends in ${integration.secret_last_four}. Creating another key disables the old one.` : "Only your server should use this key."}</small></p></div><button type="button" className="brand-button" onClick={createSecret} disabled={secretBusy}>{secretBusy ? "Creating..." : integration.configured ? "Rotate server key" : "Create server key"}<ProductIcon name="arrow" /></button></div>
            )}
            {secretError ? <p className="auth-error" role="alert">{secretError}</p> : null}
          </article>
          <article id="confirm-event">
            <header><span>04</span><div><small>Your backend</small><h2>Confirm the customer result</h2><p>Send one event only after your own system confirms it happened. Use a unique ID so retries are never counted twice.</p></div></header>
            <div className="tracking-code-controls">
              <label><span>Result</span><select value={eventType} onChange={(event) => setEventType(event.target.value)}>{serverEventTypes.map((type) => <option key={type} value={type}>{labels[type]}</option>)}</select></label>
              <div role="tablist" aria-label="Code language">{(["node", "python", "curl"] as CodeLanguage[]).map((item) => <button type="button" role="tab" aria-selected={language === item} className={language === item ? "is-active" : ""} onClick={() => setLanguage(item)} key={item}>{item === "node" ? "Node.js" : item === "python" ? "Python" : "cURL"}</button>)}</div>
            </div>
            <div className="tracking-code tracking-code--server"><div><span>{language === "node" ? "Node.js" : language === "python" ? "Python" : "Terminal"}</span><CopyButton value={confirmCode} /></div><pre><code>{confirmCode}</code></pre></div>
            <div className="tracking-event-health"><span><i /><strong>{integration.events_received ? "Events are arriving" : "Waiting for the first event"}</strong></span><small>Last received: {formatDate(integration.last_event_at)}</small></div>
          </article></> : null}
        </div>
      </section>
    </div>
  );
}
