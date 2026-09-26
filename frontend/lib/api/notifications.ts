import { api } from "./client";

export interface NotificationOut {
  id: string;
  kind: string;
  title: string;
  body: string;
  link: string | null;
  read: boolean;
  created_at: string;
}

export interface NotificationList {
  unread_count: number;
  items: NotificationOut[];
}

export interface UnreadCountOut {
  unread_count: number;
}

export const NOTIFICATIONS_CHANGED = "clippit:notifications-changed";

export function announceNotificationsChanged() {
  if (typeof window !== "undefined") window.dispatchEvent(new Event(NOTIFICATIONS_CHANGED));
}

export const notificationsApi = {
  list: (params?: { unread_only?: boolean; limit?: number; before?: string }) => {
    const query = new URLSearchParams();
    if (params?.unread_only) query.set("unread_only", "true");
    if (params?.limit) query.set("limit", String(params.limit));
    if (params?.before) query.set("before", params.before);
    const text = query.toString();
    return api.get<NotificationList>(`/notifications${text ? `?${text}` : ""}`);
  },

  markRead: (id: string) => api.post<NotificationOut>(`/notifications/${id}/read`, {}),

  markAllRead: () => api.post<void>("/notifications/read-all", {}),

  archive: (id: string) => api.post<void>(`/notifications/${id}/archive`, {}),

  unreadCount: () => api.get<UnreadCountOut>("/notifications/unread-count"),
};
