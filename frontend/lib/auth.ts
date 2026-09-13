export type AccountRole = "creator" | "organisation";
export type CompletionKind = "signup" | "signin" | "recovery";

export interface AuthRouteMeta {
  label: string;
  count: string;
  progress: number;
}

export const authRouteMeta: Record<string, AuthRouteMeta> = {
  "/auth/sign-up": { label: "Your account", count: "01 / 03", progress: 33 },
  "/auth/sign-up/creator": {
    label: "Your details",
    count: "02 / 03",
    progress: 66,
  },
  "/auth/sign-up/organisation": {
    label: "Your details",
    count: "02 / 03",
    progress: 66,
  },
  "/auth/verify-email": {
    label: "Email check",
    count: "03 / 03",
    progress: 100,
  },
  "/auth/sign-in": { label: "Secure sign in", count: "01 / 01", progress: 100 },
  "/auth/forgot-password": {
    label: "Account recovery",
    count: "01 / 03",
    progress: 33,
  },
  "/auth/recovery-code": {
    label: "Account recovery",
    count: "02 / 03",
    progress: 66,
  },
  "/auth/reset-password": {
    label: "Account recovery",
    count: "03 / 03",
    progress: 100,
  },
  "/auth/success": { label: "All sorted", count: "03 / 03", progress: 100 },
};

export const isEmail = (value: string) => /^\S+@\S+\.\S+$/.test(value.trim());
export const isStrongPassword = (value: string) =>
  value.length >= 8 && /\d/.test(value);
