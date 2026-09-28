"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import { AnimatedNumber } from "@/components/ui/AnimatedNumber";
import { ClippitEmptyState } from "@/components/ui/ClippitEmptyState";
import { ButtonLoader, ClippitLoader } from "@/components/ui/ClippitLoader";
import { ProductIcon } from "@/components/ui/ProductIcon";
import { ReceiptHeader } from "@/components/ui/ReceiptHeader";
import { campaignsApi, type CampaignOut, type FundingOrderOut } from "@/lib/api/campaigns";
import { errorMessage } from "@/lib/api/client";

export function CampaignFundedScreen() {
  const [slug, setSlug] = useState("");
  const [campaign, setCampaign] = useState<CampaignOut | null>(null);
  const [order, setOrder] = useState<FundingOrderOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const campaignSlug = window.localStorage.getItem("clippit:last-created-campaign") ?? "";
    setSlug(campaignSlug);
    if (!campaignSlug) { setError("No recently created campaign was found."); setLoading(false); return; }
    Promise.all([campaignsApi.get(campaignSlug), campaignsApi.funding(campaignSlug)])
      .then(([campaignData, fundingData]) => { setCampaign(campaignData); setOrder(fundingData); })
      .catch((err) => setError(errorMessage(err, "We couldn't load the funding order.")))
      .finally(() => setLoading(false));
  }, []);

  const confirm = async () => {
    if (!slug || confirming) return;
    setConfirming(true); setError("");
    try {
      const updated = await campaignsApi.confirmFunding(slug);
      setOrder(updated);
      setCampaign(await campaignsApi.get(slug));
    } catch (err) { setError(errorMessage(err, "Payment has not been confirmed yet.")); }
    finally { setConfirming(false); }
  };

  if (loading) return <div className="brand-page"><ClippitLoader contained tone="gold" label="Checking the funding order" /></div>;
  if (!campaign || !order) return <div className="brand-page"><ClippitEmptyState tone="danger" icon="wallet" title="Funding order unavailable" copy={error || "Open the campaign list and select the campaign again."} action={<Link href="/brand/campaigns">Open campaigns<ProductIcon name="arrow" /></Link>} /></div>;

  const confirmed = order.status === "confirmed" || campaign.status === "active";
  return <div className="brand-page funded-page"><section className="funded-hero"><div className="funded-art">{campaign.cover_image_url ? <div className="funded-cover"><Image src={campaign.cover_image_url} alt={`${campaign.title} campaign cover`} fill unoptimized sizes="420px" /></div> : <Image src="/assets/illustrations/clippit-icons/funding-pot.webp" alt="" width={300} height={300} />}<span><ProductIcon name={confirmed ? "check" : "clock"} /></span></div><span className={`brand-status brand-status--${confirmed ? "lime" : "gold"}`}>{confirmed ? "Funds confirmed" : order.status.replaceAll("_", " ")}</span><h1>{confirmed ? "Campaign funded" : "Complete the payment"}</h1><p>{confirmed ? `${campaign.title} is live and ready for creators.` : `The campaign opens only after ${order.total.toLocaleString("en-NG", { style: "currency", currency: "NGN" })} is confirmed.`}</p>{error && <p className="auth-error" role="alert">{error}</p>}<div>{confirmed ? <Link className="brand-button" href={`/brand/campaigns/${campaign.slug}`}>View campaign<ProductIcon name="arrow" /></Link> : <>{order.checkout_url && <a className="brand-button" href={order.checkout_url}>Continue to secure payment<ProductIcon name="arrow" /></a>}<button className="brand-button brand-button--dark" type="button" onClick={() => void confirm()} disabled={confirming}>{confirming ? <ButtonLoader label="Checking payment" /> : <>Check payment status<ProductIcon name="check" /></>}</button></>}<Link className="brand-button brand-button--dark" href="/brand/campaigns">Back to campaigns<ProductIcon name="campaigns" /></Link></div></section><aside className="funded-ticket"><ReceiptHeader title="Campaign funding order" reference={order.reference} /><dl><div><dt>Campaign</dt><dd>{campaign.title}</dd></div><div><dt>Creator pot</dt><dd><AnimatedNumber value={order.pot} format="money" /></dd></div><div><dt>Clippit campaign fee</dt><dd><AnimatedNumber value={order.fee} format="money" /></dd></div><div><dt>Total</dt><dd><AnimatedNumber value={order.total} format="money" /></dd></div><div><dt>Payment method</dt><dd>{order.method}</dd></div><div><dt>Provider</dt><dd>{order.provider}</dd></div><div><dt>Status</dt><dd>{order.status.replaceAll("_", " ")}</dd></div></dl>{order.collection && <section className="funded-bank-details"><small>Pay into</small><strong>{order.collection.bank_name}</strong><b>{order.collection.account_number}</b><span>{order.collection.account_name}</span></section>}<footer><ProductIcon name="shield" /><span><strong>Server-issued funding record</strong><small>The campaign opens only after the payment provider confirms this order.</small></span></footer></aside></div>;
}
