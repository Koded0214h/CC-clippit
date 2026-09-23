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

export const notificationsApi = {
  list: () => api.get<NotificationList>("/notifications"),

  markRead: (id: string) => api.post<void>(`/notifications/${id}/read`, {}),

  markAllRead: () => api.post<void>("/notifications/read-all", {}),

  archive: (id: string) => api.post<void>(`/notifications/${id}/archive`, {}),

  unreadCount: () => api.get<UnreadCountOut>("/notifications/unread-count"),
};
