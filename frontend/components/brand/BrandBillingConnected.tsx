"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { ClippitEmptyState } from "@/components/ui/ClippitEmptyState";
import { ButtonLoader, ClippitLoader } from "@/components/ui/ClippitLoader";
import { ProductIcon } from "@/components/ui/ProductIcon";
import { banksApi, type BankOut } from "@/lib/api/bankDetails";
import { walletApi, type OrganisationBankAccountOut } from "@/lib/api/account";
import { errorMessage } from "@/lib/api/client";
import { organisationsApi, type OrganisationProfileOut, type OrganisationTransactionOut } from "@/lib/api/organisations";
import { formatDate } from "@/lib/format";
import { money } from "@/lib/product";

export function BrandBillingScreen() {
  const [profile, setProfile] = useState<OrganisationProfileOut | null>(null);
  const [transactions, setTransactions] = useState<OrganisationTransactionOut[] | null>(null);
  const [bank, setBank] = useState<OrganisationBankAccountOut | null>(null);
  const [banks, setBanks] = useState<BankOut[]>([]);
  const [editing, setEditing] = useState(false);
  const [bankEditing, setBankEditing] = useState(false);
  const [draft, setDraft] = useState({ name: "", website: "", finance_email: "" });
  const [bankDraft, setBankDraft] = useState({ bank_code: "", account_number: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = () => Promise.all([
    organisationsApi.getProfile(),
    organisationsApi.transactions({ kind: "funding", limit: 100 }),
    walletApi.getOrganisationBank().catch(() => null),
    banksApi.list().catch(() => []),
  ]).then(([profileData, transactionData, bankData, bankList]) => {
    setProfile(profileData); setTransactions(transactionData.items); setBank(bankData); setBanks(bankList);
    setDraft({ name: profileData.name, website: profileData.website ?? "", finance_email: profileData.finance_email ?? "" });
    setBankDraft((current) => ({ ...current, bank_code: bankData?.bank_code ?? bankList[0]?.code ?? "" }));
  });

  useEffect(() => { load().catch((err) => setError(errorMessage(err, "We couldn't load billing details."))); }, []);

  const saveProfile = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setError("");
    try { setProfile(await organisationsApi.updateProfile(draft)); setEditing(false); }
    catch (err) { setError(errorMessage(err, "Billing details could not be updated.")); }
    finally { setBusy(false); }
  };

  const saveBank = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setError("");
    const selected = banks.find((item) => item.code === bankDraft.bank_code);
    if (!selected) {
      setError("The bank list is unavailable. Try again later.");
      setBusy(false);
      return;
    }
    try {
      await walletApi.saveOrganisationBank({ bank_code: bankDraft.bank_code, bank_name: selected.name, account_number: bankDraft.account_number });
      setBank(await walletApi.verifyOrganisationBank()); setBankEditing(false); setBankDraft((current) => ({ ...current, account_number: "" }));
    } catch (err) { setError(errorMessage(err, "The bank account could not be saved and verified.")); }
    finally { setBusy(false); }
  };

  if (error && !profile) return <div className="brand-page"><ClippitEmptyState tone="danger" icon="brief" title="Billing unavailable" copy={error} /></div>;
  if (!profile || transactions === null) return <div className="brand-page"><ClippitLoader contained tone="gold" label="Loading billing and funding records" /></div>;
  return <div className="brand-page completion-workspace billing-page"><header className="customer-head"><div><h1>Billing and funding records</h1><p>{profile.business_legal_name ?? profile.name} · Nigerian naira</p></div></header>{error && <p className="auth-error" role="alert">{error}</p>}<section className="billing-identity"><div><span><ProductIcon name="building" /></span><p><small>Billing identity</small><strong>{profile.business_legal_name ?? profile.name}</strong><em>{profile.finance_email ?? "No finance email added"}</em><em>{profile.website ?? "No website added"}</em></p></div><span className={`brand-status brand-status--${profile.business_verified ? "lime" : "gold"}`}>{profile.business_verified ? "Verified" : "Not verified"}</span><button type="button" onClick={() => setEditing(true)}>Edit billing details</button></section>{editing && <form className="billing-editor" onSubmit={saveProfile}><header><div><small>Organisation profile</small><h2>Edit billing details</h2></div><button type="button" onClick={() => setEditing(false)} aria-label="Close billing editor"><ProductIcon name="more" /></button></header><div className="billing-editor__grid"><label><span>Organisation name</span><input required value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} /></label><label><span>Billing email</span><input required type="email" value={draft.finance_email} onChange={(event) => setDraft({ ...draft, finance_email: event.target.value })} /></label><label><span>Website</span><input value={draft.website} onChange={(event) => setDraft({ ...draft, website: event.target.value })} /></label></div><footer><button type="button" onClick={() => setEditing(false)}>Cancel</button><button className="completion-submit" type="submit" disabled={busy}>{busy ? <ButtonLoader label="Saving" /> : <>Save changes<ProductIcon name="check" /></>}</button></footer></form>}<section className="billing-identity"><div><span><ProductIcon name="bank" /></span><p><small>Withdrawal account</small><strong>{bank?.bank_name ?? "No bank account"}</strong><em>{bank?.account_number_masked ?? "Add the organisation's account"}</em><em>{bank?.account_name ?? ""}</em></p></div>{bank && <span className={`brand-status brand-status--${bank.verified ? "lime" : "gold"}`}>{bank.verified ? "Verified" : "Not verified"}</span>}<button type="button" onClick={() => setBankEditing(true)}>{bank ? "Change account" : "Add account"}</button></section>{bankEditing && <form className="billing-editor" onSubmit={saveBank}><header><div><small>Organisation bank account</small><h2>Save and verify account</h2></div><button type="button" onClick={() => setBankEditing(false)} aria-label="Close bank editor"><ProductIcon name="more" /></button></header><div className="billing-editor__grid"><label><span>Bank</span><select value={bankDraft.bank_code} onChange={(event) => setBankDraft({ ...bankDraft, bank_code: event.target.value })}>{banks.map((item) => <option value={item.code} key={item.code}>{item.name}</option>)}</select></label><label><span>Account number</span><input required inputMode="numeric" value={bankDraft.account_number} onChange={(event) => setBankDraft({ ...bankDraft, account_number: event.target.value.replace(/\D/g, "").slice(0, 20) })} /></label></div><footer><button type="button" onClick={() => setBankEditing(false)}>Cancel</button><button className="completion-submit" type="submit" disabled={busy || bankDraft.account_number.length < 6}>{busy ? <ButtonLoader label="Verifying" /> : <>Save and verify<ProductIcon name="check" /></>}</button></footer></form>}<section className="invoice-stack"><header><div><h2>Campaign fee records</h2><p>Funding transactions issued by the live ledger.</p></div></header>{!transactions.length && <ClippitEmptyState size="inline" tone="gold" icon="brief" title="No funding records yet" copy="A record appears after you create a campaign funding order." />}{transactions.map((transaction) => <Link href={`/brand/invoices/${transaction.id}`} key={transaction.id}><span><ProductIcon name="brief" /></span><p><small>{transaction.reference} · {formatDate(transaction.created_at)}</small><strong>Campaign funding · {transaction.campaign_title}</strong></p><b>{money(transaction.fee ?? 0)}</b><span className={`brand-status brand-status--${transaction.status === "confirmed" ? "lime" : "gold"}`}>{transaction.status}</span><ProductIcon name="arrow" /></Link>)}</section></div>;
}

export function BrandInvoiceScreen({ id }: { id: string }) {
  const [transaction, setTransaction] = useState<OrganisationTransactionOut | null>(null);
  const [profile, setProfile] = useState<OrganisationProfileOut | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { Promise.all([organisationsApi.transaction(id), organisationsApi.getProfile()]).then(([item, profileData]) => { setTransaction(item); setProfile(profileData); }).catch((err) => setError(errorMessage(err, "We couldn't load this funding record."))); }, [id]);
  if (error) return <div className="brand-page"><ClippitEmptyState tone="danger" icon="brief" title="Funding record unavailable" copy={error} /></div>;
  if (!transaction || !profile) return <div className="brand-page"><ClippitLoader contained tone="gold" label="Loading funding record" /></div>;
  const fee = transaction.fee ?? 0;
  return <div className="brand-page completion-workspace"><header className="customer-head"><div><Link className="customer-back" href="/brand/billing"><ProductIcon name="chevron" />Back</Link><h1>Campaign funding record</h1></div><button className="statement-download" onClick={() => window.print()}>Download PDF<ProductIcon name="brief" /></button></header><article className="official-invoice"><header><div><Image src="/assets/clippit-mark.png" width={58} height={58} alt="" /><span><strong>Clippit</strong><small>Campaign funding record</small></span></div><p><small>Reference</small><strong>{transaction.reference}</strong><span>Issued {formatDate(transaction.created_at)}</span></p></header><section className="invoice-parties"><div><small>Billed to</small><strong>{profile.business_legal_name ?? profile.name}</strong><span>{profile.finance_email ?? "No finance email"}</span><span>{profile.website ?? ""}</span></div><div><small>Processed by</small><strong>Clippit</strong><span>{transaction.provider}</span><span>{transaction.provider_reference ?? "Provider reference pending"}</span></div></section><table><thead><tr><th>Description</th><th>Reference</th><th>Amount</th></tr></thead><tbody><tr><td>Creator campaign pot<br /><small>{transaction.campaign_title}</small></td><td>{transaction.campaign_id}</td><td>{money(transaction.amount)}</td></tr><tr><td>Clippit campaign fee</td><td>{transaction.reference}</td><td>{money(fee)}</td></tr></tbody><tfoot><tr><td colSpan={2}>Total</td><td>{money(transaction.amount + fee)}</td></tr></tfoot></table><footer><span><ProductIcon name="check" /></span><p><strong>{transaction.status}</strong><small>{transaction.settled_at ? `Settled ${formatDate(transaction.settled_at)}` : "Awaiting settlement"}</small></p><i>CLIPPIT · {transaction.reference} · CLIPPIT</i></footer></article></div>;
}
