"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ClippitEmptyState } from "@/components/ui/ClippitEmptyState";
import { ClippitLoader } from "@/components/ui/ClippitLoader";
import { ProductIcon, type ProductIconName } from "@/components/ui/ProductIcon";
import { ApiError } from "@/lib/api/client";
import {
  announceNotificationsChanged,
  notificationsApi,
  type NotificationOut,
} from "@/lib/api/notifications";

type NoticeKind = "Campaigns" | "Review" | "Money" | "Account";
type Notice = {
  id: string;
  kind: NoticeKind;
  icon: ProductIconName;
  title: string;
  copy: string;
  time: string;
  href: string;
  unread: boolean;
  createdAt: string;
};

const PAGE_SIZE = 30;

function kindFor(value: string): NoticeKind {
  const kind = value.toLowerCase();
  if (["money", "earning", "payout", "withdrawal", "wallet", "funding", "refund"].some((word) => kind.includes(word))) return "Money";
  if (["review", "submission", "appeal"].some((word) => kind.includes(word))) return "Review";
  if (["account", "security", "social", "verification"].some((word) => kind.includes(word))) return "Account";
  return "Campaigns";
}

function iconFor(kind: NoticeKind): ProductIconName {
  if (kind === "Money") return "wallet";
  if (kind === "Review") return "eye";
  if (kind === "Account") return "shield";
  return "brief";
}

function relativeTime(value: string) {
  const timestamp = new Date(value).getTime();
  if (!Number.isFinite(timestamp)) return "";
  const minutes = Math.max(0, Math.floor((Date.now() - timestamp) / 60000));
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hr`;
  const days = Math.floor(hours / 24);
  return days === 1 ? "Yesterday" : `${days} days ago`;
}

function mapNotice(item: NotificationOut): Notice {
  const kind = kindFor(item.kind);
  return {
    id: item.id,
    kind,
    icon: iconFor(kind),
    title: item.title,
    copy: item.body,
    time: relativeTime(item.created_at),
    href: item.link ?? "",
    unread: !item.read,
    createdAt: item.created_at,
  };
}

export function BrandNotificationsConnected() {
  const router = useRouter();
  const [filter, setFilter] = useState<"All" | NoticeKind>("All");
  const [notices, setNotices] = useState<Notice[] | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    notificationsApi
      .list({ limit: PAGE_SIZE })
      .then((data) => {
        setNotices(data.items.map(mapNotice));
        setHasMore(data.items.length === PAGE_SIZE);
      })
      .catch((reason) => setError(reason instanceof ApiError ? reason.detail : "We couldn't load your notifications."));
  }, []);

  if (!notices && !error) return <div className="brand-page"><ClippitLoader contained tone="gold" label="Checking brand notifications" note="" /></div>;

  const rows = notices ?? [];
  const visible = rows.filter((notice) => filter === "All" || notice.kind === filter);
  const unread = rows.filter((notice) => notice.unread).length;

  const markAllRead = async () => {
    const previous = rows;
    setNotices(rows.map((notice) => ({ ...notice, unread: false })));
    setError("");
    try {
      await notificationsApi.markAllRead();
      announceNotificationsChanged();
    } catch {
      setNotices(previous);
      setError("We couldn't mark those notifications as read. Try again.");
    }
  };

  const openNotice = async (notice: Notice) => {
    if (notice.unread) {
      setNotices(rows.map((item) => item.id === notice.id ? { ...item, unread: false } : item));
      try {
        await notificationsApi.markRead(notice.id);
        announceNotificationsChanged();
      } catch {
        setError("We couldn't update that notification.");
      }
    }
    if (notice.href) router.push(notice.href);
  };

  const loadOlder = async () => {
    const last = rows.at(-1);
    if (!last) return;
    setLoadingMore(true);
    setError("");
    try {
      const data = await notificationsApi.list({ limit: PAGE_SIZE, before: last.createdAt });
      setNotices([...rows, ...data.items.map(mapNotice)]);
      setHasMore(data.items.length === PAGE_SIZE);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.detail : "We couldn't load older notifications.");
    } finally {
      setLoadingMore(false);
    }
  };

  return <div className="brand-page customer-page notifications-page brand-notifications-page">
    <header className="customer-head"><div><h1>Notifications</h1><p>Reviews, campaign updates, money movement and account checks.</p></div><button className="customer-text-button" type="button" onClick={markAllRead} disabled={!unread}>Mark all as read</button></header>
    {error && <p className="auth-error" role="alert">{error}</p>}
    <section className="notification-console">
      <aside className="notification-tally"><span><ProductIcon name="bell" /><i>{unread}</i></span><strong>{unread ? `${unread} new` : "All read"}</strong><small>Latest account activity</small><div>{(["All", "Review", "Campaigns", "Money", "Account"] as const).map((item) => <button type="button" className={filter === item ? "is-active" : ""} onClick={() => setFilter(item)} key={item}>{item}</button>)}</div></aside>
      <div className="notification-tape">
        {!visible.length && <ClippitEmptyState className="notification-tape__empty" size="compact" tone="gold" icon="bell" title={rows.length ? `No ${filter.toLowerCase()} notifications` : "You're all caught up"} copy={rows.length ? "Choose another filter to see the rest of your updates." : "Reviews, campaign changes and money updates will appear here."} />}
        {visible.map((notice) => <a href={notice.href || undefined} className={notice.unread ? "is-unread" : ""} onClick={(event) => { event.preventDefault(); void openNotice(notice); }} key={notice.id}><span className={`notice-icon notice-icon--${notice.kind.toLowerCase()}`}><ProductIcon name={notice.icon} /></span><p><small>{notice.kind}</small><strong>{notice.title}</strong><span>{notice.copy}</span></p><time>{notice.time}</time><ProductIcon name="arrow" /></a>)}
        {hasMore && <button type="button" className="customer-text-button" disabled={loadingMore} onClick={loadOlder}>{loadingMore ? "Loading..." : "Show older notifications"}</button>}
      </div>
    </section>
  </div>;
}
