"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { AnimatedNumber } from "@/components/ui/AnimatedNumber";
import { ProductIcon } from "@/components/ui/ProductIcon";
import { ClippitLoader } from "@/components/ui/ClippitLoader";
import { MINIMUM_WALLET_WITHDRAWAL } from "@/lib/fees";
import { money } from "@/lib/product";
import { walletApi, type CreatorWalletOut } from "@/lib/api/account";
import { bankDetailsApi, type BankAccountOut } from "@/lib/api/bankDetails";
import { earningsApi } from "@/lib/api/earnings";
import { payoutsApi } from "@/lib/api/payouts";
import { errorMessage } from "@/lib/api/client";
import { formatDate } from "@/lib/format";

function WalletHeading({ title, copy, back, actions }: { title: string; copy: string; back?: string; actions?: ReactNode }) {
  return <header className="wallet-page-head"><div>{back && <Link href={back}><ProductIcon name="chevron" />Back</Link>}<h1>{title}</h1><p>{copy}</p></div>{actions}</header>;
}

function Money({ value, delay = 0 }: { value: number; delay?: number }) {
  return <AnimatedNumber value={value} format="money" delay={delay} />;
}

const brandMovements = [
  { id: "REF-00812", label: "Campaign refund", detail: "Campus chop stories", amount: 42800, credit: true },
  { id: "CLP-0926-041", label: "Campaign funding", detail: "No long thing", amount: 500000, credit: false },
  { id: "FEE-00419", label: "Campaign fee", detail: "No long thing", amount: 75000, credit: false },
];

export function BrandWalletScreen() {
  return <div className="brand-page wallet-page wallet-page--brand">
    <WalletHeading title="Brand wallet" copy="Add money, withdraw available funds and see what is reserved for campaigns." actions={<div className="wallet-head-actions"><Link className="wallet-action wallet-action--dark" href="/brand/wallet/withdraw">Withdraw<ProductIcon name="bank" /></Link><Link className="wallet-action" href="/brand/wallet/fund">Add money<ProductIcon name="arrow" /></Link></div>} />
    <section className="wallet-console">
      <div className="wallet-console__balance"><span className="wallet-console__icon"><ProductIcon name="wallet" /></span><p><small>Available balance</small><strong><Money value={920000} /></strong><em>Ready for campaign funding or withdrawal</em></p><Image src="/assets/illustrations/clippit-icons/funding-pot.webp" alt="" width={170} height={170} aria-hidden="true" /></div>
      <div className="wallet-console__allocation"><header><span>Where the money is</span><strong><Money value={1232500} /></strong></header><div className="wallet-allocation-track" aria-label="Wallet allocation"><i style={{ width: "49.3%" }} /><i style={{ width: "25.4%" }} /><i style={{ width: "25.3%" }} /></div><dl><div><dt><i />Available to withdraw</dt><dd><Money value={607500} /></dd></div><div><dt><i />Reserved in campaign pots</dt><dd><Money value={312500} /></dd></div><div><dt><i />Available for campaigns</dt><dd><Money value={312500} /></dd></div></dl><p><ProductIcon name="clock" />A <Money value={42800} /> campaign refund is still processing.</p></div>
    </section>
    <section className="wallet-body-grid">
      <div className="wallet-movements"><header><div><h2>Recent wallet activity</h2><p>Money entering or leaving the Brand wallet.</p></div><Link href="/brand/transactions">All transactions<ProductIcon name="arrow" /></Link></header>{brandMovements.map((item) => <Link href={`/brand/transactions/${item.id}`} key={item.id}><span><ProductIcon name={item.credit ? "arrow" : "wallet"} /></span><p><strong>{item.label}</strong><small>{item.detail} · {item.id}</small></p><b className={item.credit ? "is-credit" : ""}>{item.credit ? "+" : "−"}{money(item.amount)}</b><ProductIcon name="chevron" /></Link>)}</div>
      <aside className="wallet-account-card"><span><ProductIcon name="bank" /></span><small>Withdrawal account</small><h2>Wema Bank</h2><strong>•••• 0193</strong><p>Gbedu Records Limited</p><div><ProductIcon name="check" />Verified company account</div><Link href="/brand/billing">Manage billing details<ProductIcon name="arrow" /></Link></aside>
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
    walletApi.get().then(setWallet).catch((err) => setError(errorMessage(err)));
    bankDetailsApi.get().then(setBank).catch(() => setBank(null));
    Promise.all([earningsApi.history({ limit: 5 }).catch(() => null), payoutsApi.list({ limit: 5 }).catch(() => null)]).then(([history, payouts]) => {
      const earned: CreatorMovement[] = (history?.items ?? []).map((row) => ({
        key: `e-${row.id}`, href: "/dashboard/earnings", label: row.state === "Payable" ? "Clip earning cleared" : row.state === "Paid" ? "Clip earning paid out" : "Clip earning in review",
        detail: `${row.brand ?? row.campaign_title} · ${row.clip}`, amount: row.amount, state: row.state === "Payable" ? "Available" : row.state === "Accrued" ? "Held" : row.state, credit: true, at: row.date,
      }));
      const paidOut: CreatorMovement[] = (payouts?.items ?? []).map((payout) => ({
        key: `p-${payout.id}`, href: `/dashboard/payouts/receipt?id=${payout.id}`, label: "Withdrawal to bank", detail: `${payout.destination.bank_name} · ${payout.reference}`,
        amount: payout.amount, state: payout.status === "succeeded" ? "Sent" : payout.status === "failed" ? "Failed" : "Processing", credit: false, at: payout.initiated_at,
      }));
      setMovements([...earned, ...paidOut].sort((a, b) => b.at.localeCompare(a.at)).slice(0, 6));
    });
  }, []);

  if (error) return <div className="dashboard-page wallet-page"><div className="campaign-empty" role="alert"><ProductIcon name="wallet" /><h2>We couldn&apos;t load your wallet.</h2><p>{error}</p></div></div>;
  if (!wallet) return <div className="dashboard-page"><ClippitLoader contained label="Opening your wallet" note="Checking available money, held earnings and transfers." /></div>;

  const total = wallet.available + wallet.held + wallet.processing;
  const pct = (value: number) => (total > 0 ? `${(value / total) * 100}%` : "0%");

  return <div className="dashboard-page wallet-page wallet-page--creator">
    <WalletHeading title="Your wallet" copy="See what you can withdraw now and what is still in review." actions={<Link className="wallet-action" href="/dashboard/withdraw">Withdraw money<ProductIcon name="bank" /></Link>} />
    <section className="wallet-console">
      <div className="wallet-console__balance"><span className="wallet-console__icon"><ProductIcon name="wallet" /></span><p><small>Available to withdraw</small><strong><Money value={wallet.available} /></strong><em>{wallet.available >= wallet.min_withdrawal ? "From approved clips and verified views" : `Withdrawals start at ${money(wallet.min_withdrawal)}`}</em></p><Image src="/assets/illustrations/clippit-icons/payout-wallet.webp" alt="" width={170} height={170} aria-hidden="true" /></div>
      <div className="wallet-console__allocation"><header><span>Money status</span><strong><Money value={total} /></strong></header><div className="wallet-allocation-track" aria-label="Creator wallet allocation"><i style={{ width: pct(wallet.available) }} /><i style={{ width: pct(wallet.held) }} /><i style={{ width: pct(wallet.processing) }} /></div><dl><div><dt><i />Available now</dt><dd><Money value={wallet.available} /></dd></div><div><dt><i />In review window</dt><dd><Money value={wallet.held} /></dd></div><div><dt><i />Processing</dt><dd><Money value={wallet.processing} /></dd></div></dl><p><ProductIcon name="shield" />Paid out so far: {money(wallet.paid_all_time)}. Only approved, verified views enter your wallet.</p></div>
    </section>
    <section className="wallet-body-grid">
      <div className="wallet-movements"><header><div><h2>Recent wallet activity</h2><p>New earnings and transfers.</p></div><Link href="/dashboard/earnings">Earning history<ProductIcon name="arrow" /></Link></header>
        {!movements.length && <p className="wallet-movements__empty">No wallet activity yet. Earnings from approved clips show up here.</p>}
        {movements.map((item) => <Link href={item.href} key={item.key}><span><ProductIcon name={item.credit ? (item.state === "Held" ? "clock" : "check") : "bank"} /></span><p><strong>{item.label}</strong><small>{item.detail} · {formatDate(item.at, { day: "numeric", month: "short" })}</small></p><b className={item.credit && item.state === "Available" ? "is-credit" : ""}>{item.credit ? "+" : "−"}{money(item.amount)}</b><em>{item.state}</em></Link>)}
      </div>
      <aside className="wallet-account-card"><span><ProductIcon name="bank" /></span><small>Payout account</small>
        {bank === undefined ? <p>Loading…</p> : bank ? <><h2>{bank.bank_name}</h2><strong>•••• {bank.account_number_masked.slice(-4)}</strong><p>{bank.account_name ?? "Name pending"}</p><div><ProductIcon name={bank.verified ? "check" : "shield"} />{bank.verified ? "Verified payout account" : "Needs verification before you withdraw"}</div><Link href="/dashboard/payout-account">{bank.verified ? "Change payout account" : "Verify account"}<ProductIcon name="arrow" /></Link></>
          : <><h2>No account yet</h2><p>Add the bank account your earnings should land in.</p><Link href="/dashboard/payout-account">Add payout account<ProductIcon name="arrow" /></Link></>}
      </aside>
    </section>
  </div>;
}

export function BrandWalletWithdrawScreen() {
  const available = 607500;
  const [amount, setAmount] = useState("100000");
  const [complete, setComplete] = useState(false);
  const requested = Math.min(available, Math.max(0, Number(amount) || 0));
  const valid = requested >= MINIMUM_WALLET_WITHDRAWAL;
  const submit = (event: FormEvent) => { event.preventDefault(); if (valid) setComplete(true); };
  return <div className="brand-page wallet-page wallet-operation-page">
    <WalletHeading back="/brand/wallet" title={complete ? "Withdrawal requested" : "Withdraw from Brand wallet"} copy={complete ? "Track the transfer from Transactions." : "Send available Brand wallet money to the verified company account."} />
    {complete ? <section className="wallet-operation-success"><span><ProductIcon name="check" /></span><small>Withdrawal reference · BWD-0923-118</small><h2><Money value={requested} /></h2><p>Wema Bank · •••• 0193</p><div><Link className="wallet-action wallet-action--dark" href="/brand/transactions">View transaction<ProductIcon name="arrow" /></Link><Link className="wallet-action" href="/brand/wallet">Back to wallet<ProductIcon name="wallet" /></Link></div></section> : <div className="wallet-operation-grid"><form className="wallet-operation-form" onSubmit={submit}><div className="wallet-form-balance"><small>Available to withdraw</small><strong><Money value={available} /></strong><span><ProductIcon name="check" />Cleared</span></div><label><span>Amount to withdraw</span><div><b>₦</b><input value={amount} onChange={(event) => setAmount(event.target.value.replace(/\D/g, "").slice(0, 9))} inputMode="numeric" aria-label="Brand wallet withdrawal amount" /></div></label><div className="wallet-amount-chips">{[50000, 100000, available].map((value) => <button type="button" className={requested === value ? "is-active" : ""} onClick={() => setAmount(String(value))} key={value}>{value === available ? "All" : money(value)}</button>)}</div><section className="wallet-destination"><span><ProductIcon name="bank" /></span><p><small>Send to</small><strong>Wema Bank · •••• 0193</strong><em>Gbedu Records Limited</em></p><ProductIcon name="check" /></section><dl className="wallet-operation-summary"><div><dt>Wallet withdrawal</dt><dd><Money value={requested} /></dd></div><div><dt>Withdrawal fee</dt><dd>₦0</dd></div><div><dt>Sent to bank</dt><dd><Money value={requested} /></dd></div></dl><button className="wallet-action" disabled={!valid} type="submit">Confirm withdrawal<ProductIcon name="arrow" /></button></form><aside className="wallet-operation-note"><Image src="/assets/illustrations/clippit-icons/withdraw-bank.webp" alt="" width={280} height={280} /><h2>Before you withdraw</h2><p>The bank account must belong to the verified organisation. Transfers normally arrive within 24 hours.</p><span><ProductIcon name="shield" />Account details are checked before the transfer starts.</span></aside></div>}
  </div>;
}

export function BrandWalletFundScreen() {
  const [amount, setAmount] = useState("250000");
  const [complete, setComplete] = useState(false);
  const deposit = Math.max(0, Number(amount) || 0);
  const valid = deposit >= 5000;
  const submit = (event: FormEvent) => { event.preventDefault(); if (valid) setComplete(true); };
  return <div className="brand-page wallet-page wallet-operation-page">
    <WalletHeading back="/brand/wallet" title={complete ? "Money added" : "Add money to Brand wallet"} copy={complete ? "The new balance is ready for campaign funding." : "Add money before funding or topping up a campaign."} />
    {complete ? <section className="wallet-operation-success"><span><ProductIcon name="check" /></span><small>Wallet funding reference · BWF-0923-219</small><h2><Money value={deposit} /></h2><p>Added to Gbedu Records Brand wallet</p><div><Link className="wallet-action wallet-action--dark" href="/brand/wallet">Open wallet<ProductIcon name="wallet" /></Link><Link className="wallet-action" href="/brand/campaigns/new">Create campaign<ProductIcon name="arrow" /></Link></div></section> : <div className="wallet-operation-grid"><form className="wallet-operation-form" onSubmit={submit}><div className="wallet-form-balance"><small>Current wallet balance</small><strong><Money value={920000} /></strong><span><ProductIcon name="shield" />Protected</span></div><label><span>Amount to add</span><div><b>₦</b><input value={amount} onChange={(event) => setAmount(event.target.value.replace(/\D/g, "").slice(0, 9))} inputMode="numeric" aria-label="Amount to add to Brand wallet" /></div></label><div className="wallet-amount-chips">{[100000, 250000, 500000].map((value) => <button type="button" className={deposit === value ? "is-active" : ""} onClick={() => setAmount(String(value))} key={value}>{money(value)}</button>)}</div><section className="wallet-destination"><span><ProductIcon name="bank" /></span><p><small>Payment method</small><strong>Secure card or bank payment</strong><em>Complete payment on the next step</em></p><ProductIcon name="chevron" /></section><dl className="wallet-operation-summary"><div><dt>Added to wallet</dt><dd><Money value={deposit} /></dd></div><div><dt>Payment fee</dt><dd>₦0</dd></div><div><dt>Total to pay</dt><dd><Money value={deposit} /></dd></div></dl><button className="wallet-action" disabled={!valid} type="submit">Continue to payment<ProductIcon name="arrow" /></button></form><aside className="wallet-operation-note"><Image src="/assets/illustrations/clippit-icons/funding-pot.webp" alt="" width={280} height={280} /><h2>Wallet money stays flexible</h2><p>Use the balance to fund a new campaign, top up a live one or withdraw available money later.</p><span><ProductIcon name="shield" />Campaign money becomes reserved only after you approve a funding order.</span></aside></div>}
  </div>;
}
