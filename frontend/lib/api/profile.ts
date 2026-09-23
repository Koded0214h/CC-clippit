import { api } from "./client";

export interface NotificationSettings {
  new_campaigns: boolean;
  submission_verdicts: boolean;
  earnings_payable: boolean;
  campaign_closing: boolean;
  funding_alerts: boolean;
  review_alerts: boolean;
  weekly_report: boolean;
}

export interface PreferencesOut {
  email_notifications: boolean;
  marketing_emails: boolean;
  theme: string;
  notifications: NotificationSettings;
}

export interface PreferencesUpdate {
  email_notifications?: boolean;
  marketing_emails?: boolean;
  theme?: string;
  notifications?: Partial<NotificationSettings>;
}

export const profileApi = {
  getPreferences: () => api.get<PreferencesOut>("/profile/preferences"),
  updatePreferences: (payload: PreferencesUpdate) => api.patch<PreferencesOut>("/profile/preferences", payload),
};
