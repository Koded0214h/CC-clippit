"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import { AnimatedNumber } from "@/components/ui/AnimatedNumber";
import { ClippitEmptyState } from "@/components/ui/ClippitEmptyState";
import { ButtonLoader, ClippitLoader } from "@/components/ui/ClippitLoader";
import { ProductIcon } from "@/components/ui/ProductIcon";
import { ReceiptHeader } from "@/components/ui/ReceiptHeader";
import { campaignsApi, type CampaignOut, type CampaignStats, type CampaignSubmissionRow, type RefundOut } from "@/lib/api/campaigns";
import { errorMessage } from "@/lib/api/client";
import { formatDate } from "@/lib/format";
import { money } from "@/lib/product";

type RecordData = { campaign: CampaignOut; stats: CampaignStats; submissions: CampaignSubmissionRow[]; refunds: RefundOut[] };

async function loadRecord(slug: string): Promise<RecordData> {
  const [campaign, stats, submissions, refunds] = await Promise.all([
    campaignsApi.get(slug),
    campaignsApi.getStats(slug),
    campaignsApi.getSubmissions(slug, 100),
    campaignsApi.refunds(slug),
  ]);
  return { campaign, stats, submissions, refunds };
}

export function CampaignCloseoutScreen({ slug }: { slug: string }) {
  const [data, setData] = useState<RecordData | null>(null);
  const [error, setError] = useState("");
  const [exporting, setExporting] = useState(false);
  useEffect(() => { loadRecord(slug).then(setData).catch((err) => setError(errorMessage(err, "We couldn't load this campaign report."))); }, [slug]);
  if (error) return <div className="brand-page customer-page"><ClippitEmptyState tone="danger" icon="brief" title="Report unavailable" copy={error} /></div>;
  if (!data) return <div className="brand-page"><ClippitLoader contained tone="gold" label="Building the campaign report" /></div>;
  const { campaign, stats, submissions, refunds } = data;
  const refunded = refunds.filter((item) => item.status === "succeeded").reduce((sum, item) => sum + item.amount, 0);
  const exportCsv = async () => {
    if (exporting) return;
    setExporting(true);
    setError("");
    try {
      const report = await campaignsApi.downloadReport(campaign.slug);
      const url = URL.createObjectURL(report);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${campaign.slug}-report.csv`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (reason) {
      setError(errorMessage(reason, "We couldn't download the campaign report."));
    } finally {
      setExporting(false);
    }
  };
  const top = [...submissions].sort((a, b) => b.verified_views - a.verified_views).slice(0, 3);
  return <div className="brand-page customer-page closeout-page"><header className="customer-head"><div><Link className="customer-back" href={`/brand/campaigns/${campaign.slug}`}><ProductIcon name="chevron" />Back</Link><h1>{campaign.status === "closed" ? "Campaign closeout" : "Campaign report"}</h1><p>Current delivery and money record for {campaign.title}.</p></div><button className="brand-button" type="button" onClick={exportCsv} disabled={exporting} aria-busy={exporting}>{exporting ? "Preparing report…" : "Download report"}<ProductIcon name="brief" /></button></header><section className="closeout-hero"><div><span><ProductIcon name={campaign.status === "closed" ? "check" : "campaigns"} /></span><small>{campaign.phase} · created {formatDate(campaign.created_at)}</small><h2>{campaign.title}</h2><p>{campaign.description}</p></div><div className="closeout-stamp">{campaign.cover_image_url ? <Image src={campaign.cover_image_url} alt="" width={220} height={220} unoptimized /> : <Image src="/assets/illustrations/clippit-icons/verified-proof.webp" alt="" width={220} height={220} />}<strong>{campaign.status === "closed" ? "Closed" : "Live record"}</strong></div></section><section className="closeout-receipt"><ReceiptHeader title="Campaign performance record" reference={campaign.id} /><div className="closeout-money"><p><small>Campaign pot</small><strong><AnimatedNumber value={campaign.pot} format="money" /></strong></p><i /><p><small>Earned by creators</small><strong><AnimatedNumber value={campaign.spent} format="money" /></strong></p><i /><p><small>Returned to wallet</small><strong><AnimatedNumber value={refunded} format="money" /></strong></p></div><div className="closeout-proof"><article><small>Verified views</small><strong><AnimatedNumber value={stats.verified_views} format="compact" /></strong><span>from platform readings</span></article><article><small>Approved clips</small><strong><AnimatedNumber value={stats.approved} /></strong><span>of {stats.submissions} submissions</span></article><article><small>Needs review</small><strong><AnimatedNumber value={stats.review} /></strong><span>waiting for a brand decision</span></article><article><small>Pot remaining</small><strong>{money(stats.remaining)}</strong><span>{stats.percent_remaining}% available</span></article></div></section><div className="closeout-grid"><section className="top-delivery"><header><h2>Top clips</h2><p>Highest verified delivery.</p></header>{!top.length && <ClippitEmptyState size="inline" tone="gold" icon="play" title="No submissions yet" copy="Approved submissions will appear in this report." />}{top.map((item, index) => <article key={item.id}><b>{index + 1}</b><span>{item.creator_name.slice(0, 2).toUpperCase()}</span><p><strong>{item.creator_name}</strong><small><AnimatedNumber value={item.verified_views} format="compact" /> verified views · {money(item.earned)}</small></p></article>)}</section><section className="platform-delivery"><header><h2>Selected metrics</h2><p>Verified campaign totals.</p></header>{campaign.performance_metrics.map((metric) => <div key={metric.metric_type}><span><ProductIcon name={metric.metric_type === "view" ? "eye" : metric.metric_type === "purchase" ? "wallet" : "spark"} /></span><p><strong>{metric.metric_type}</strong><small><AnimatedNumber value={stats.performance[metric.metric_type] ?? 0} format="compact" /> verified</small></p><em>{money(metric.rate_amount)} / {metric.unit_size}</em></div>)}</section></div></div>;
}

export function CampaignRefundScreen({ slug }: { slug: string }) {
  const [data, setData] = useState<RecordData | null>(null);
  const [reason, setReason] = useState("");
  const [agree, setAgree] = useState(false);
  const [refund, setRefund] = useState<RefundOut | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { loadRecord(slug).then((loaded) => { setData(loaded); setRefund(loaded.refunds[0] ?? null); }).catch((err) => setError(errorMessage(err))); }, [slug]);
  const submit = async () => {
    if (!data || !agree || !reason.trim() || busy) return;
    setBusy(true); setError("");
    try {
      if (data.campaign.status !== "closed") await campaignsApi.close(slug);
      const created = await campaignsApi.requestRefund(slug, reason.trim());
      setRefund(created);
      setData(await loadRecord(slug));
    } catch (err) { setError(errorMessage(err, "The campaign could not be closed and refunded.")); }
    finally { setBusy(false); }
  };
  if (error && !data) return <div className="brand-page"><ClippitEmptyState tone="danger" icon="wallet" title="Closeout unavailable" copy={error} /></div>;
  if (!data) return <div className="brand-page"><ClippitLoader contained tone="gold" label="Checking refundable campaign money" /></div>;
  const { campaign } = data;
  if (refund) return <div className="brand-page completion-workspace"><section className="completion-result completion-result--workspace"><Image src="/assets/illustrations/clippit-icons/withdraw-bank.webp" width={240} height={240} alt="" /><span className="brand-status brand-status--lime">{refund.status}</span><h1>{money(refund.amount)} returned to your Brand wallet.</h1><p>Refund reference {refund.id}. The wallet and transaction ledger now use this server record.</p><Link className="brand-button" href="/brand/transactions">Track in transactions<ProductIcon name="arrow" /></Link></section></div>;
  return <div className="brand-page completion-workspace"><header className="customer-head"><div><Link className="customer-back" href={`/brand/campaigns/${slug}`}><ProductIcon name="chevron" />Back</Link><h1>Close campaign</h1><p>Close creator earning first, then calculate the eligible wallet refund.</p></div></header><section className="refund-sheet"><div className="refund-tally"><small>Unused campaign money</small><strong><AnimatedNumber value={campaign.remaining} format="money" /></strong><span>before the closeout calculation</span><div><i style={{ width: `${campaign.pot > 0 ? (campaign.spent / campaign.pot) * 100 : 0}%` }} /><b /></div><p><span>Earned by creators</span><b>{money(campaign.spent)}</b></p><p><span>Unspent campaign pot</span><b>{money(campaign.remaining)}</b></p></div><aside><h2>Closeout confirmation</h2><dl><div><dt>Campaign</dt><dd>{campaign.title}</dd></div><div><dt>Unspent balance</dt><dd>{money(campaign.remaining)}</dd></div><div><dt>Wallet refund</dt><dd>Calculated by the server after closeout</dd></div></dl><label><span>Reason for closing</span><textarea value={reason} onChange={(event) => setReason(event.target.value)} rows={4} placeholder="Why are you ending this campaign?" /></label><label><input type="checkbox" checked={agree} onChange={(event) => setAgree(event.target.checked)} />I understand that recognised creator earnings will not be reversed.</label>{error && <p className="auth-error" role="alert">{error}</p>}<button className="completion-submit" onClick={() => void submit()} disabled={!agree || !reason.trim() || busy || campaign.remaining <= 0}>{busy ? <ButtonLoader label="Closing campaign" /> : <>Close and calculate refund<ProductIcon name="arrow" /></>}</button></aside></section></div>;
}
