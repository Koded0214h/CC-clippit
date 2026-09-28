"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ClippitEmptyState } from "@/components/ui/ClippitEmptyState";
import { ClippitLoader } from "@/components/ui/ClippitLoader";
import { ProductIcon } from "@/components/ui/ProductIcon";
import { brandApi, type ReviewCard } from "@/lib/api/brand";
import { errorMessage } from "@/lib/api/client";
import { formatDateTime, platformLabel } from "@/lib/format";

export function BrandReviewDetailScreen({ id }: { id: string }) {
  const [review, setReview] = useState<ReviewCard | null>(null);
  const [decision, setDecision] = useState<"approve" | "changes" | null>(null);
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(true);
  const [acting, setActing] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    brandApi.getReview(id).then(setReview).catch((err) => setError(errorMessage(err, "We couldn't load this submission."))).finally(() => setLoading(false));
  }, [id]);

  const approve = async () => {
    if (acting) return;
    setActing(true); setError("");
    try { await brandApi.approveReview(id); setDecision("approve"); }
    catch (err) { setError(errorMessage(err, "The submission could not be approved.")); }
    finally { setActing(false); }
  };

  const requestCorrection = async () => {
    if (acting || !reason.trim()) return;
    setActing(true); setError("");
    try { await brandApi.requestCorrection(id, reason.trim()); setDecision("changes"); }
    catch (err) { setError(errorMessage(err, "The correction request could not be sent.")); }
    finally { setActing(false); }
  };

  if (loading) return <div className="brand-page"><ClippitLoader contained tone="gold" label="Loading the submission" /></div>;
  if (error && !review) return <div className="brand-page"><ClippitEmptyState tone="danger" icon="eye" title="Submission unavailable" copy={error} action={<Link href="/brand/reviews">Back to reviews<ProductIcon name="arrow" /></Link>} /></div>;
  if (!review) return null;
  if (decision) return <div className="brand-page review-resolved"><span className="review-resolved__icon"><ProductIcon name={decision === "approve" ? "check" : "eye"} /></span><h1>{decision === "approve" ? "Clip approved" : "Correction requested"}</h1><p>{decision === "approve" ? "The creator's submission is approved and its verified performance can be processed." : "The creator can now correct this submission and send it again."}</p><Link className="brand-button" href="/brand/reviews">Back to review queue<ProductIcon name="arrow" /></Link></div>;

  return <div className="brand-page review-detail-page">
    <Link className="brand-back" href="/brand/reviews"><ProductIcon name="chevron" />Back to review queue</Link>
    <header><div><span className="brand-status brand-status--gold">{review.is_appeal ? "Appeal" : "Needs review"}</span><h1>{review.title ?? review.campaign_title}</h1><p>{review.creator_name}{review.creator_handle ? ` · @${review.creator_handle.replace(/^@/, "")}` : ""} · {platformLabel(review.platform)}</p></div><div className="confidence-ticket"><span>Submitted</span><strong>{formatDateTime(review.submitted_at)}</strong><small>{review.campaign_title}</small></div></header>
    <div className="review-detail-grid"><section className="submission-player"><div>{review.video_url ? <video src={review.video_url} controls playsInline /> : <Image src="/assets/illustrations/clippit-icons/clip-submit.webp" alt="" fill sizes="(max-width: 900px) 100vw, 50vw" />} </div><p><span><i>{review.creator_name.slice(0, 2).toUpperCase()}</i><strong>{review.creator_name}</strong><small>Connected {platformLabel(review.platform)} account</small></span><a href={review.url} target="_blank" rel="noreferrer">Open public post<ProductIcon name="link" /></a></p></section><aside className="review-evidence"><span className="review-evidence__icon"><ProductIcon name="eye" /></span><div><small>Review note</small><h2>{review.issue ?? "Check this submission against the campaign brief."}</h2></div></aside></div>
    <section className="decision-sheet"><header><div><h2>Record your decision</h2><p>Approve the submission or tell the creator exactly what needs correcting.</p></div></header><label className="review-correction-field"><span>Correction reason</span><textarea value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Explain the campaign requirement that needs attention" rows={4} /></label>{error && <p className="auth-error" role="alert">{error}</p>}<div className="decision-actions"><button type="button" className="brand-button brand-button--dark" disabled={acting || !reason.trim()} onClick={() => void requestCorrection()}>Request a correction<ProductIcon name="arrow" /></button><button type="button" className="brand-button" disabled={acting} onClick={() => void approve()}>Approve this clip<ProductIcon name="check" /></button></div></section>
  </div>;
}
