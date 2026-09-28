"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { AnimatedNumber } from "@/components/ui/AnimatedNumber";
import { ClippitEmptyState } from "@/components/ui/ClippitEmptyState";
import { ClippitLoader } from "@/components/ui/ClippitLoader";
import { ProductIcon } from "@/components/ui/ProductIcon";
import { ReceiptHeader } from "@/components/ui/ReceiptHeader";
import { ApiError } from "@/lib/api/client";
import { organisationsApi, type OrganisationTransactionOut } from "@/lib/api/organisations";
import { formatDate } from "@/lib/format";
import { money } from "@/lib/product";

function ScreenHead({ title, copy, action }: { title: string; copy: string; action?: ReactNode }) {
  return <header className="customer-head"><div><h1>{title}</h1><p>{copy}</p></div>{action}</header>;
}

function label(kind: string) {
  return kind === "refund" ? "Refund" : kind === "funding" ? "Funding" : kind.replaceAll("_", " ");
}

function signedAmount(transaction: OrganisationTransactionOut) {
  const gross = transaction.amount + (transaction.fee ?? 0);
  return transaction.kind === "refund" ? gross : -gross;
}

function TransactionReceipt({ transaction, fullPage = false }: { transaction: OrganisationTransactionOut; fullPage?: boolean }) {
  const refund = transaction.kind === "refund";
  const signed = signedAmount(transaction);
  return <aside className={`transaction-ticket${fullPage ? " transaction-ticket--full" : ""}`}>
    <ReceiptHeader title="Official transaction receipt" reference={transaction.reference} />
    <div className="transaction-ticket__subject"><span><Image src={refund ? "/assets/illustrations/clippit-icons/withdraw-bank.webp" : "/assets/illustrations/clippit-icons/funding-pot.webp"} width={82} height={82} alt="" /></span><p><small>{label(transaction.kind)}</small><strong>{signed > 0 ? "+" : "−"}{money(Math.abs(signed))}</strong><em><ProductIcon name="check" />{transaction.status}</em><time>{formatDate(transaction.settled_at ?? transaction.created_at, { dateStyle: "medium", timeStyle: "short" })}</time></p></div>
    <div className="transaction-ticket__parties"><section><h2>Recipient</h2><p><strong>{refund ? "Your organisation wallet" : "Clippit Campaign Escrow"}</strong><span>{refund ? "Returned campaign balance" : "Creator campaign pot"}</span></p></section><section><h2>Sender</h2><p><strong>{refund ? "Clippit Campaign Escrow" : "Your organisation"}</strong><span>{transaction.provider}</span></p></section></div>
    <section className="transaction-ticket__information"><h2>Transaction information</h2><dl><div><dt>Transaction type</dt><dd>{label(transaction.kind)}</dd></div><div><dt>Transaction ID</dt><dd>{transaction.id}</dd></div><div><dt>Provider reference</dt><dd>{transaction.provider_reference ?? "Not assigned"}</dd></div><div><dt>Campaign</dt><dd>{transaction.campaign_title}</dd></div><div><dt>Campaign ID</dt><dd>{transaction.campaign_id}</dd></div><div><dt>Campaign fee</dt><dd>{transaction.fee == null ? "Not applicable" : money(transaction.fee)}</dd></div><div><dt>Settlement currency</dt><dd>Nigerian naira</dd></div></dl></section>
    <div className="transaction-ticket__verified"><ProductIcon name="shield" /><span><strong>Verify this receipt</strong><small>{typeof window !== "undefined" ? window.location.host : "clippit.click"}/verify/{transaction.reference}</small></span></div>
    <Link href={`/brand/campaigns/${transaction.campaign_id}`}>Open campaign<ProductIcon name="arrow" /></Link><button type="button" onClick={() => window.print()}>Download receipt<ProductIcon name="brief" /></button>
  </aside>;
}

export function BrandTransactionsScreen() {
  const router = useRouter();
  const [filter, setFilter] = useState("All");
  const [transactions, setTransactions] = useState<OrganisationTransactionOut[] | null>(null);
  const [selected, setSelected] = useState<OrganisationTransactionOut | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    organisationsApi.transactions({ limit: 100 }).then((data) => {
      setTransactions(data.items);
      setSelected(data.items[0] ?? null);
    }).catch((err) => setError(err instanceof ApiError ? err.detail : "We couldn't load transactions."));
  }, []);

  if (error) return <div className="brand-page customer-page"><ClippitEmptyState tone="danger" icon="brief" title="We couldn't load transactions" copy={error} /></div>;
  if (transactions === null) return <div className="brand-page"><ClippitLoader contained tone="gold" label="Loading your transactions" /></div>;

  const visible = transactions.filter((item) => filter === "All" || label(item.kind) === filter);
  const funded = transactions.filter((item) => item.kind === "funding").reduce((sum, item) => sum + item.amount, 0);
  const fees = transactions.reduce((sum, item) => sum + (item.fee ?? 0), 0);
  const returned = transactions.filter((item) => item.kind === "refund").reduce((sum, item) => sum + item.amount, 0);
  const exportStatement = () => {
    if (!transactions.length) return;
    const rows = [["reference", "type", "campaign", "amount", "fee", "status", "provider", "created_at"], ...transactions.map((item) => [item.reference, item.kind, item.campaign_title, String(item.amount), String(item.fee ?? ""), item.status, item.provider, item.created_at])];
    const csv = rows.map((row) => row.map((value) => `"${String(value).replaceAll('"', '""')}"`).join(",")).join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = url; anchor.download = "clippit-transactions.csv"; anchor.click(); URL.revokeObjectURL(url);
  };

  return <div className="brand-page customer-page brand-transactions-page">
    <ScreenHead title="Transactions" copy="Campaign funding and refunds recorded for this organisation." action={<div className="brand-transaction-actions"><Link className="brand-button brand-button--dark" href="/brand/wallet">Open wallet<ProductIcon name="wallet" /></Link><button className="brand-button" type="button" onClick={exportStatement} disabled={!transactions.length}>Export statement<ProductIcon name="brief" /></button></div>} />
    <section className="transaction-balance"><div><small>Money recorded</small><strong><AnimatedNumber value={funded + fees + returned} format="money" /></strong><span><ProductIcon name="brief" />From your live transaction ledger</span></div><dl><div><dt>Creator pots funded</dt><dd><AnimatedNumber value={funded} format="money" /></dd></div><div><dt>Campaign fees</dt><dd><AnimatedNumber value={fees} format="money" /></dd></div><div><dt>Returned</dt><dd><AnimatedNumber value={returned} format="money" /></dd></div></dl></section>
    {!transactions.length ? <ClippitEmptyState tone="gold" icon="brief" title="No transactions yet" copy="Campaign funding and refunds will appear here when they happen." action={<Link className="brand-button" href="/brand/campaigns/new">Create campaign<ProductIcon name="arrow" /></Link>} /> : <div className="transaction-workspace"><section className="transaction-ledger"><header><div>{["All", "Funding", "Refund"].map((item) => <button type="button" className={filter === item ? "is-active" : ""} onClick={() => setFilter(item)} key={item}>{item}</button>)}</div><span>{visible.length} records</span></header><div className="transaction-labels"><span>Reference</span><span>Campaign</span><span>Date</span><span>Amount</span><span>Status</span></div>{visible.map((item) => { const signed = signedAmount(item); return <button type="button" className={`transaction-row${selected?.id === item.id ? " is-selected" : ""}`} onClick={() => window.matchMedia("(max-width: 900px)").matches ? router.push(`/brand/transactions/${item.id}`) : setSelected(item)} key={item.id}><span><i><ProductIcon name={item.kind === "refund" ? "arrow" : "wallet"} /></i><b>{label(item.kind)}</b><small>{item.reference}</small></span><strong>{item.campaign_title}</strong><time>{formatDate(item.created_at)}</time><em className={signed > 0 ? "is-credit" : ""}>{signed > 0 ? "+" : "−"}{money(Math.abs(signed))}</em><u>{item.status}</u></button>; })}</section>{selected && <TransactionReceipt transaction={selected} />}</div>}
  </div>;
}

export function BrandTransactionReceiptScreen({ transactionId }: { transactionId: string }) {
  const [transaction, setTransaction] = useState<OrganisationTransactionOut | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    organisationsApi.transaction(transactionId).then(setTransaction).catch((err) => setError(err instanceof ApiError ? err.detail : "We couldn't load this transaction."));
  }, [transactionId]);
  if (error) return <div className="brand-page customer-page"><ClippitEmptyState tone="danger" icon="brief" title="Transaction unavailable" copy={error} action={<Link href="/brand/transactions">Back to transactions<ProductIcon name="arrow" /></Link>} /></div>;
  if (!transaction) return <div className="brand-page"><ClippitLoader contained tone="gold" label="Loading transaction receipt" /></div>;
  return <div className="brand-page customer-page transaction-receipt-page"><Link className="brand-back" href="/brand/transactions"><ProductIcon name="chevron" />Back to transactions</Link><TransactionReceipt transaction={transaction} fullPage /></div>;
}
