"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { AnimatedNumber } from "@/components/ui/AnimatedNumber";
import { ProductIcon } from "@/components/ui/ProductIcon";
import { ClippitLoader } from "@/components/ui/ClippitLoader";
import { ClippitEmptyState } from "@/components/ui/ClippitEmptyState";
import { money } from "@/lib/product";
import {
  walletApi,
  type BrandWalletOut,
  type BrandWithdrawalOut,
  type CreatorWalletOut,
  type OrganisationBankAccountOut,
} from "@/lib/api/account";
import { bankDetailsApi, type BankAccountOut } from "@/lib/api/bankDetails";
import { campaignsApi, type CampaignOut } from "@/lib/api/campaigns";
import { earningsApi } from "@/lib/api/earnings";
import { organisationsApi, type OrganisationTransactionOut } from "@/lib/api/organisations";
import { payoutsApi } from "@/lib/api/payouts";
import { ApiError, errorMessage } from "@/lib/api/client";
import { formatDate } from "@/lib/format";

function WalletHeading({ title, copy, back, actions }: { title: string; copy: string; back?: string; actions?: ReactNode }) {
  return <header className="wallet-page-head"><div>{back && <Link href={back}><ProductIcon name="chevron" />Back</Link>}<h1>{title}</h1><p>{copy}</p></div>{actions}</header>;
}

function Money({ value, delay = 0 }: { value: number; delay?: number }) {
  return <AnimatedNumber value={value} format="money" delay={delay} />;
}

type BrandMovement = { id: string; reference: string; label: string; detail: string; amount: number; credit: boolean; at: string; href: string };

async function optionalBank<T>(request: Promise<T>): Promise<T | null> {
  try { return await request; }
  catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}

export function BrandWalletScreen() {
  const [wallet, setWallet] = useState<BrandWalletOut | null>(null);
  const [bank, setBank] = useState<OrganisationBankAccountOut | null>(null);
  const [movements, setMovements] = useState<BrandMovement[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      walletApi.getBrand(),
      optionalBank(walletApi.getOrganisationBank()),
      organisationsApi.transactions({ limit: 6 }),
      walletApi.brandWithdrawals(6),
    ]).then(([walletData, bankData, transactionData, withdrawalData]) => {
      setWallet(walletData);
      setBank(bankData);
      const transactions = transactionData.items.map((item: OrganisationTransactionOut): BrandMovement => ({
        id: item.id,
        reference: item.reference,
        label: item.kind === "refund" ? "Campaign refund" : "Campaign funding",
        detail: item.campaign_title,
        amount: item.amount + (item.fee ?? 0),
        credit: item.kind === "refund",
        at: item.created_at,
        href: `/brand/transactions/${item.id}`,
      }));
      const withdrawals = withdrawalData.map((item): BrandMovement => ({
        id: item.id,
        reference: item.reference,
        label: "Wallet withdrawal",
        detail: item.destination.bank_name,
        amount: item.amount,
        credit: false,
        at: item.initiated_at,
        href: "/brand/transactions",
      }));
      setMovements([...transactions, ...withdrawals].sort((a, b) => b.at.localeCompare(a.at)).slice(0, 6));
    }).catch((err) => setError(errorMessage(err, "We couldn't load the Brand wallet.")));
  }, []);

  if (error) return <div className="brand-page wallet-page"><ClippitEmptyState tone="danger" icon="wallet" title="We couldn't load your wallet" copy={error} role="alert" /></div>;
  if (!wallet) return <div className="brand-page"><ClippitLoader contained tone="gold" label="Opening your Brand wallet" /></div>;

  const total = wallet.available + wallet.reserved;
  const availablePct = total > 0 ? (wallet.available / total) * 100 : 0;

  return <div className="brand-page wallet-page wallet-page--brand">
    <WalletHeading title="Brand wallet" copy="Withdraw returned campaign money and see what is still reserved." actions={<div className="wallet-head-actions"><Link className="wallet-action wallet-action--dark" href="/brand/wallet/withdraw">Withdraw<ProductIcon name="bank" /></Link><Link className="wallet-action" href="/brand/wallet/fund">Fund a campaign<ProductIcon name="arrow" /></Link></div>} />
    <section className="wallet-console">
      <div className="wallet-console__balance"><span className="wallet-console__icon"><ProductIcon name="wallet" /></span><p><small>Available to withdraw</small><strong><Money value={wallet.available} /></strong><em>{wallet.available >= wallet.min_withdrawal ? "Returned campaign money ready for withdrawal" : `Withdrawals start at ${money(wallet.min_withdrawal)}`}</em></p><Image src="/assets/illustrations/clippit-icons/funding-pot.webp" alt="" width={170} height={170} aria-hidden="true" /></div>
      <div className="wallet-console__allocation"><header><span>Where the money is</span><strong><Money value={total} /></strong></header><div className="wallet-allocation-track" aria-label="Wallet allocation"><i style={{ width: `${availablePct}%` }} /><i style={{ width: `${100 - availablePct}%` }} /></div><dl><div><dt><i />Available to withdraw</dt><dd><Money value={wallet.available} /></dd></div><div><dt><i />Reserved in campaign pots</dt><dd><Money value={wallet.reserved} /></dd></div><div><dt><i />Withdrawn all time</dt><dd><Money value={wallet.withdrawn_all_time} /></dd></div></dl><p><ProductIcon name="shield" />Reserved campaign money cannot be withdrawn while creators can still earn from it.</p></div>
    </section>
    <section className="wallet-body-grid">
      <div className="wallet-movements"><header><div><h2>Recent wallet activity</h2><p>Campaign funding, refunds and withdrawals.</p></div><Link href="/brand/transactions">All transactions<ProductIcon name="arrow" /></Link></header>{!movements.length && <ClippitEmptyState className="wallet-movements__empty" size="inline" tone="gold" icon="wallet" title="No wallet activity yet" copy="Campaign funding and refunds will appear here." />}{movements.map((item) => <Link href={item.href} key={`${item.label}-${item.id}`}><span><ProductIcon name={item.credit ? "arrow" : "wallet"} /></span><p><strong>{item.label}</strong><small>{item.detail} · {item.reference}</small></p><b className={item.credit ? "is-credit" : ""}>{item.credit ? "+" : "−"}{money(item.amount)}</b><ProductIcon name="chevron" /></Link>)}</div>
      <aside className="wallet-account-card">{bank ? <><span><ProductIcon name="bank" /></span><small>Withdrawal account</small><h2>{bank.bank_name}</h2><strong>{bank.account_number_masked}</strong><p>{bank.account_name ?? "Account name pending"}</p><div><ProductIcon name={bank.verified ? "check" : "shield"} />{bank.verified ? "Verified company account" : "Verification required"}</div><Link href="/brand/billing">Manage account<ProductIcon name="arrow" /></Link></> : <ClippitEmptyState size="inline" tone="gold" icon="bank" title="No withdrawal account" copy="Add and verify the organisation bank account before withdrawing." action={<Link href="/brand/billing">Add bank account<ProductIcon name="arrow" /></Link>} />}</aside>
    </section>
  </div>;
}

type CreatorMovement = { key: string; href: string; label: string; detail: string; amount: number; state: string; credit: boolean; at: string };

export function CreatorWalletScreen() {
  const [wallet, setWallet] = useState<CreatorWalletOut | null>(null);
  const [movements, setMovements] = useState<CreatorMovement[]>([]);
  const [bank, setBank] = useState<BankAccountOut | null | undefined>(undefined);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      walletApi.getCreator(),
      optionalBank(bankDetailsApi.get()),
      earningsApi.history({ limit: 5 }),
      payoutsApi.list({ limit: 5 }),
    ]).then(([walletData, bankData, history, payouts]) => {
      setWallet(walletData);
      setBank(bankData);
      const earned: CreatorMovement[] = history.items.map((row) => ({
        key: `e-${row.id}`, href: "/dashboard/earnings", label: row.state === "Payable" ? "Clip earning cleared" : row.state === "Paid" ? "Clip earning paid out" : "Clip earning in review",
        detail: `${row.brand ?? row.campaign_title} · ${row.clip}`, amount: row.amount, state: row.state === "Payable" ? "Available" : row.state === "Accrued" ? "Held" : row.state, credit: true, at: row.date,
      }));
      const paidOut: CreatorMovement[] = payouts.items.map((payout) => ({
        key: `p-${payout.id}`, href: `/dashboard/payouts/receipt?id=${payout.id}`, label: "Withdrawal to bank", detail: `${payout.destination.bank_name} · ${payout.reference}`,
        amount: payout.amount, state: payout.status === "succeeded" ? "Sent" : payout.status === "failed" ? "Failed" : "Processing", credit: false, at: payout.initiated_at,
      }));
      setMovements([...earned, ...paidOut].sort((a, b) => b.at.localeCompare(a.at)).slice(0, 6));
    }).catch((err) => setError(errorMessage(err, "We couldn't load your wallet activity.")));
  }, []);

  if (error) return <div className="dashboard-page wallet-page"><ClippitEmptyState tone="danger" icon="wallet" title="We couldn&apos;t load your wallet" copy={error} role="alert" /></div>;
  if (!wallet) return <div className="dashboard-page"><ClippitLoader contained label="Opening your wallet" note="Checking available money, held earnings and transfers." /></div>;

  const total = wallet.available + wallet.held + wallet.processing;
  const pct = (value: number) => (total > 0 ? `${(value / total) * 100}%` : "0%");

  return <div className="dashboard-page wallet-page wallet-page--creator">
    <WalletHeading title="Your wallet" copy="See what you can withdraw now and what is still in review." actions={<Link className="wallet-action" href="/dashboard/withdraw">Withdraw money<ProductIcon name="bank" /></Link>} />
    <section className="wallet-console">
      <div className="wallet-console__balance"><span className="wallet-console__icon"><ProductIcon name="wallet" /></span><p><small>Available to withdraw</small><strong><Money value={wallet.available} /></strong><em>{wallet.available >= wallet.min_withdrawal ? "From approved clips and verified performance" : `Withdrawals start at ${money(wallet.min_withdrawal)}`}</em></p><Image src="/assets/illustrations/clippit-icons/payout-wallet.webp" alt="" width={170} height={170} aria-hidden="true" /></div>
      <div className="wallet-console__allocation"><header><span>Money status</span><strong><Money value={total} /></strong></header><div className="wallet-allocation-track" aria-label="Creator wallet allocation"><i style={{ width: pct(wallet.available) }} /><i style={{ width: pct(wallet.held) }} /><i style={{ width: pct(wallet.processing) }} /></div><dl><div><dt><i />Available now</dt><dd><Money value={wallet.available} /></dd></div><div><dt><i />In review window</dt><dd><Money value={wallet.held} /></dd></div><div><dt><i />Processing</dt><dd><Money value={wallet.processing} /></dd></div></dl><p><ProductIcon name="shield" />Paid out so far: {money(wallet.paid_all_time)}.</p></div>
    </section>
    <section className="wallet-body-grid">
      <div className="wallet-movements"><header><div><h2>Recent wallet activity</h2><p>New earnings and transfers.</p></div><Link href="/dashboard/earnings">Earning history<ProductIcon name="arrow" /></Link></header>{!movements.length && <ClippitEmptyState className="wallet-movements__empty" size="inline" tone="gold" icon="wallet" title="No wallet activity yet" copy="Earnings from approved clips will appear here." />}{movements.map((item) => <Link href={item.href} key={item.key}><span><ProductIcon name={item.credit ? (item.state === "Held" ? "clock" : "check") : "bank"} /></span><p><strong>{item.label}</strong><small>{item.detail} · {formatDate(item.at, { day: "numeric", month: "short" })}</small></p><b className={item.credit && item.state === "Available" ? "is-credit" : ""}>{item.credit ? "+" : "−"}{money(item.amount)}</b><em>{item.state}</em></Link>)}</div>
      <aside className="wallet-account-card">{bank === undefined ? <><span><ProductIcon name="bank" /></span><small>Payout account</small><p>Loading…</p></> : bank ? <><span><ProductIcon name="bank" /></span><small>Payout account</small><h2>{bank.bank_name}</h2><strong>{bank.account_number_masked}</strong><p>{bank.account_name ?? "Name pending"}</p><div><ProductIcon name={bank.verified ? "check" : "shield"} />{bank.verified ? "Verified payout account" : "Needs verification before you withdraw"}</div><Link href="/dashboard/payout-account">{bank.verified ? "Change payout account" : "Verify account"}<ProductIcon name="arrow" /></Link></> : <ClippitEmptyState size="inline" tone="gold" icon="bank" title="No payout account yet" copy="Add the bank account your earnings should land in." action={<Link href="/dashboard/payout-account">Add payout account<ProductIcon name="arrow" /></Link>} />}</aside>
    </section>
  </div>;
}

export function BrandWalletWithdrawScreen() {
  const [wallet, setWallet] = useState<BrandWalletOut | null>(null);
  const [bank, setBank] = useState<OrganisationBankAccountOut | null>(null);
  const [amount, setAmount] = useState("");
  const [withdrawal, setWithdrawal] = useState<BrandWithdrawalOut | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [requestKey] = useState(() => crypto.randomUUID());

  useEffect(() => {
    Promise.all([walletApi.getBrand(), optionalBank(walletApi.getOrganisationBank())])
      .then(([walletData, bankData]) => { setWallet(walletData); setBank(bankData); })
      .catch((err) => setError(errorMessage(err)));
  }, []);

  if (error && !wallet) return <div className="brand-page wallet-page"><ClippitEmptyState tone="danger" icon="wallet" title="We couldn't open withdrawals" copy={error} /></div>;
  if (!wallet) return <div className="brand-page"><ClippitLoader contained tone="gold" label="Checking your available balance" /></div>;

  const available = wallet.available;
  const requested = Math.min(available, Math.max(0, Number(amount) || 0));
  const valid = requested >= wallet.min_withdrawal && !!bank?.verified;
  const fee = requested * wallet.withdrawal_fee_rate;
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!valid || submitting) return;
    setSubmitting(true); setError("");
    try {
      await walletApi.quoteBrandWithdrawal(requested, requestKey);
      setWithdrawal(await walletApi.withdrawBrand(requested, requestKey));
    } catch (err) { setError(errorMessage(err, "The withdrawal could not be started.")); }
    finally { setSubmitting(false); }
  };

  return <div className="brand-page wallet-page wallet-operation-page">
    <WalletHeading back="/brand/wallet" title={withdrawal ? "Withdrawal requested" : "Withdraw from Brand wallet"} copy={withdrawal ? "The real transfer status is shown below." : "Send available Brand wallet money to the verified company account."} />
    {withdrawal ? <section className="wallet-operation-success"><span><ProductIcon name="check" /></span><small>Withdrawal reference · {withdrawal.reference}</small><h2><Money value={withdrawal.net} /></h2><p>{withdrawal.destination.bank_name} · {withdrawal.destination.account_number_masked}</p><div className="wallet-operation-status"><ProductIcon name="clock" />{withdrawal.status}</div><div><Link className="wallet-action wallet-action--dark" href="/brand/transactions">View transactions<ProductIcon name="arrow" /></Link><Link className="wallet-action" href="/brand/wallet">Back to wallet<ProductIcon name="wallet" /></Link></div></section> : <div className="wallet-operation-grid"><form className="wallet-operation-form" onSubmit={submit}><div className="wallet-form-balance"><small>Available to withdraw</small><strong><Money value={available} /></strong><span><ProductIcon name="check" />Cleared</span></div><label><span>Amount to withdraw</span><div><b>₦</b><input value={amount} onChange={(event) => setAmount(event.target.value.replace(/\D/g, "").slice(0, 9))} inputMode="numeric" aria-label="Brand wallet withdrawal amount" /></div></label><div className="wallet-amount-chips">{[50000, 100000, available].filter((value, index, all) => value > 0 && all.indexOf(value) === index).map((value) => <button type="button" className={requested === value ? "is-active" : ""} onClick={() => setAmount(String(value))} key={value}>{value === available ? "All" : money(value)}</button>)}</div>{bank ? <section className="wallet-destination"><span><ProductIcon name="bank" /></span><p><small>Send to</small><strong>{bank.bank_name} · {bank.account_number_masked}</strong><em>{bank.account_name ?? "Account name pending"}</em></p><ProductIcon name={bank.verified ? "check" : "shield"} /></section> : <ClippitEmptyState size="inline" tone="gold" icon="bank" title="Add a bank account first" copy="The organisation needs a verified withdrawal account." action={<Link href="/brand/billing">Add bank account<ProductIcon name="arrow" /></Link>} />}<dl className="wallet-operation-summary"><div><dt>Wallet withdrawal</dt><dd><Money value={requested} /></dd></div><div><dt>Withdrawal fee</dt><dd><Money value={fee} /></dd></div><div><dt>Sent to bank</dt><dd><Money value={requested - fee} /></dd></div></dl>{error && <p className="auth-error" role="alert">{error}</p>}<button className="wallet-action" disabled={!valid || submitting} type="submit">{submitting ? "Starting transfer…" : "Confirm withdrawal"}<ProductIcon name="arrow" /></button></form><aside className="wallet-operation-note"><Image src="/assets/illustrations/clippit-icons/withdraw-bank.webp" alt="" width={280} height={280} /><h2>Before you withdraw</h2><p>The bank account must belong to the verified organisation. Transfers normally arrive within 24 hours.</p><span><ProductIcon name="shield" />The final fee and destination are verified by the server.</span></aside></div>}
  </div>;
}

export function BrandWalletFundScreen() {
  const [campaigns, setCampaigns] = useState<CampaignOut[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    campaignsApi.list({ limit: 100 }).then((rows) => setCampaigns(rows.filter((campaign) => ["draft", "pending_funding"].includes(campaign.status)))).catch((err) => setError(errorMessage(err)));
  }, []);
  return <div className="brand-page wallet-page wallet-operation-page">
    <WalletHeading back="/brand/wallet" title="Fund a campaign" copy="Payments belong to a specific campaign and use its server-calculated funding quote." />
    {error ? <ClippitEmptyState tone="danger" icon="wallet" title="We couldn't load campaigns" copy={error} /> : campaigns === null ? <ClippitLoader contained tone="gold" label="Checking campaigns that need funding" /> : campaigns.length ? <section className="wallet-funding-campaigns">{campaigns.map((campaign) => <Link href={`/brand/campaigns/${campaign.slug}`} key={campaign.id}><span><ProductIcon name="campaigns" /></span><p><small>{campaign.status === "pending_funding" ? "Waiting for payment" : "Draft campaign"}</small><strong>{campaign.title}</strong><em>{money(campaign.pot)} creator pot</em></p><ProductIcon name="arrow" /></Link>)}</section> : <ClippitEmptyState tone="gold" icon="campaigns" title="No campaign needs funding" copy="Create a campaign first. Its real funding quote and payment options appear after review." action={<Link className="wallet-action" href="/brand/campaigns/new">Create campaign<ProductIcon name="arrow" /></Link>} />}
  </div>;
}
