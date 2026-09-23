import { api } from "./client";
import type { AccountRole } from "@/lib/auth";

export interface UserOut {
  id: string;
  email: string;
  full_name: string;
  role: AccountRole;
  created_at: string;
  email_verified: boolean;
  onboarding_completed: boolean;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string | null;
  token_type: string;
  user: UserOut;
}

export interface CodeSentResponse {
  sent: boolean;
  resend_in: number;
}

export interface ResetTokenResponse {
  reset_token: string;
}

export interface SessionOut {
  id: string;
  device_label: string | null;
  ip_address: string | null;
  created_at: string;
  last_seen_at: string;
  current: boolean;
}

export interface RevokedCountOut {
  revoked: number;
}

export interface StepUpChallengeOut {
  challenge_token: string;
}

export interface StepUpTokenOut {
  step_up_token: string;
}

export function storeTokens(
  data: Pick<TokenResponse, "access_token" | "refresh_token">,
) {
  localStorage.setItem("clippit:access-token", data.access_token);
  if (data.refresh_token) {
    localStorage.setItem("clippit:refresh-token", data.refresh_token);
  }
}

export function clearTokens() {
  localStorage.removeItem("clippit:access-token");
  localStorage.removeItem("clippit:refresh-token");
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("clippit:access-token");
}

export const authApi = {
  signup: (payload: {
    email: string;
    password: string;
    full_name: string;
    role: AccountRole;
  }) => api.post<TokenResponse>("/auth/signup", payload),

  login: (payload: { email: string; password: string }) =>
    api.post<TokenResponse>("/auth/login", payload),

  logout: () => api.post<void>("/auth/logout", {}),

  me: () => api.get<UserOut>("/auth/me"),

  verifyEmail: (payload: { code: string; email?: string }) =>
    api.post<UserOut>("/auth/verify-email", payload),

  resendVerification: (payload?: { email?: string }) =>
    api.post<CodeSentResponse>("/auth/verify-email/resend", payload ?? {}),

  forgotPassword: (payload: { email: string }) =>
    api.post<CodeSentResponse>("/auth/forgot-password", payload),

  verifyRecoveryCode: (payload: { email: string; code: string }) =>
    api.post<ResetTokenResponse>("/auth/recovery-code/verify", payload),

  resetPassword: (payload: { reset_token: string; password: string }) =>
    api.post<void>("/auth/reset-password", payload),

  refresh: (payload: { refresh_token: string }) =>
    api.post<TokenResponse>("/auth/refresh", payload),

  changePassword: (payload: {
    current_password: string;
    new_password: string;
    revoke_other_sessions?: boolean;
  }) => api.post<void>("/auth/change-password", payload),

  getSessions: () => api.get<SessionOut[]>("/auth/sessions"),

  revokeSession: (sessionId: string) =>
    api.delete<void>(`/auth/sessions/${sessionId}`),

  revokeOtherSessions: () =>
    api.delete<RevokedCountOut>("/auth/sessions/others"),

  requestStepUp: (payload: { action: string }) =>
    api.post<StepUpChallengeOut>("/auth/step-up/request", payload),

  verifyStepUp: (payload: { challenge_token: string; password: string }) =>
    api.post<StepUpTokenOut>("/auth/step-up/verify", payload),

  deleteAccount: (payload: { step_up_token: string }) =>
    api.delete<void>("/auth/account", payload),
};
