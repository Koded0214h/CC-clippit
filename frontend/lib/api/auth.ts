import { api } from "./client";
import type { AccountRole } from "@/lib/auth";
import {
  clearStoredTokens,
  getAccessToken as readAccessToken,
  promoteSessionTokens,
  storeTokenPair,
  type TokenPersistence,
} from "./tokenStorage";

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
  remembered: boolean;
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

export interface RememberDeviceOut {
  remembered: boolean;
  expires_in_days: number;
}

export function storeTokens(
  data: Pick<TokenResponse, "access_token" | "refresh_token">,
  persistence: TokenPersistence = "persistent",
) {
  storeTokenPair(data, persistence);
}

export function clearTokens() {
  clearStoredTokens();
}

export function getAccessToken(): string | null {
  return readAccessToken();
}

export function rememberCurrentDevice() {
  return promoteSessionTokens();
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

  requestRememberDevice: () =>
    api.post<CodeSentResponse>("/auth/remember-device/request", {}),

  verifyRememberDevice: (code: string) =>
    api.post<RememberDeviceOut>("/auth/remember-device/verify", { code }),

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
