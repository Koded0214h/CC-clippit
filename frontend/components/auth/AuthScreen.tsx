"use client";

import { useState, type InputHTMLAttributes, type ReactNode } from "react";
import { Icon } from "@/components/ui/Icon";
import { ButtonLoader } from "@/components/ui/ClippitLoader";

type FieldIcon = "building" | "lock" | "mail";

interface FieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: ReactNode;
  error?: string;
  hint?: string;
  icon?: FieldIcon;
}

export function TextField({ label, error, hint, icon, ...props }: FieldProps) {
  return (
    <label className={`field${error ? " has-error" : ""}`}>
      <span>{label}</span>
      <span className="field__control">
        {icon && <Icon name={icon} />}
        <input {...props} aria-invalid={Boolean(error)} required />
      </span>
      {hint && <small className="field__hint">{hint}</small>}
      <small className="field__error">{error}</small>
    </label>
  );
}

export function PasswordField({
  label,
  error,
  hint,
  icon = "lock",
  name = "password",
  ...props
}: FieldProps) {
  const [visible, setVisible] = useState(false);
  return (
    <label className={`field${error ? " has-error" : ""}`}>
      <span>{label}</span>
      <span className="field__control">
        <Icon name={icon} />
        <input
          {...props}
          name={name}
          type={visible ? "text" : "password"}
          aria-invalid={Boolean(error)}
          required
        />
        <button
          className="password-toggle"
          type="button"
          onClick={() => setVisible((value) => !value)}
          aria-label={visible ? "Hide password" : "Show password"}
        >
          <Icon name={visible ? "eye-off" : "eye"} />
        </button>
      </span>
      {hint && <small className="field__hint">{hint}</small>}
      <small className="field__error">{error}</small>
    </label>
  );
}

export function AuthButton({
  children,
  disabled,
  loading = false,
  loadingLabel = "Working on it",
}: {
  children: ReactNode;
  disabled?: boolean;
  loading?: boolean;
  loadingLabel?: string;
}) {
  return (
    <button className={`auth-button${loading ? " is-loading" : ""}`} type="submit" disabled={disabled || loading} aria-busy={loading}>
      {loading ? <ButtonLoader label={loadingLabel} /> : <>{children}<Icon name="arrow" /></>}
    </button>
  );
}

export function GoogleAuthButton({ intent, onClick }: { intent: "signin" | "signup"; onClick?: () => void }) {
  return (
    <button
      className="google-auth-button"
      type="button"
      data-google-auth={intent}
      onClick={onClick}
    >
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path
          fill="#4285F4"
          d="M23.49 12.27c0-.79-.07-1.55-.2-2.27H12v4.51h6.47a5.53 5.53 0 0 1-2.4 3.63v3h3.89c2.28-2.1 3.53-5.2 3.53-8.87Z"
        />
        <path
          fill="#34A853"
          d="M12 24c3.24 0 5.95-1.07 7.93-2.9l-3.89-3c-1.08.72-2.46 1.15-4.04 1.15-3.13 0-5.78-2.11-6.73-4.95H1.25v3.1A12 12 0 0 0 12 24Z"
        />
        <path
          fill="#FBBC05"
          d="M5.27 14.3A7.2 7.2 0 0 1 4.9 12c0-.8.14-1.58.38-2.3V6.6H1.25A12 12 0 0 0 0 12c0 1.93.46 3.75 1.25 5.4l4.02-3.1Z"
        />
        <path
          fill="#EA4335"
          d="M12 4.75c1.76 0 3.34.61 4.59 1.8l3.44-3.45A11.55 11.55 0 0 0 12 0 12 12 0 0 0 1.25 6.6l4.02 3.1C6.22 6.86 8.87 4.75 12 4.75Z"
        />
      </svg>
      <span>
        {intent === "signin" ? "Sign in with Google" : "Sign up with Google"}
      </span>
    </button>
  );
}

export function AuthDivider() {
  return (
    <div className="auth-divider">
      <span>or use email</span>
    </div>
  );
}
