"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  useEffect,
  useRef,
  useState,
  type ClipboardEvent,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import {
  AuthButton,
  AuthDivider,
  GoogleAuthButton,
  PasswordField,
  TextField,
} from "./AuthScreen";
import { useAuthFlow } from "./AuthFlowProvider";
import { Icon } from "@/components/ui/Icon";
import { isEmail, isStrongPassword, type AccountRole } from "@/lib/auth";
import { ApiError } from "@/lib/api/client";
import { authApi, storeTokens } from "@/lib/api/auth";
import { homeFor, onboardingApi, onboardingFor } from "@/lib/api/onboarding";
import { saveStoredProfile } from "@/components/ui/ProfilePhotoPicker";

type Errors = Record<string, string>;

const VERIFY_EMAIL_KEY = "clippit:verify-email";
const VERIFY_AUTOSEND_KEY = "clippit:verify-autosend";

function rememberVerifyEmail(email: string, autosend = false) {
  try {
    window.sessionStorage.setItem(VERIFY_EMAIL_KEY, email);
    if (autosend) window.sessionStorage.setItem(VERIFY_AUTOSEND_KEY, "1");
  } catch {
    // private mode: the in-memory flow state still carries the email
  }
}

async function hydrateStoredProfile(role: AccountRole) {
  try {
    if (role === "organisation") {
      const profile = await onboardingApi.organisationProfile();
      saveStoredProfile("brand", { name: profile.name, bio: profile.bio ?? "", photo: profile.photo_url ?? "" });
    } else {
      const profile = await onboardingApi.creatorProfile();
      saveStoredProfile("creator", { name: profile.display_name, bio: profile.bio ?? "", photo: profile.photo_url ?? "" });
    }
  } catch {
    // the dashboard falls back to its defaults
  }
}

async function routeAfterAuth(
  router: ReturnType<typeof useRouter>,
  user: { role: AccountRole; email_verified: boolean; onboarding_completed: boolean; email: string },
) {
  if (!user.email_verified) {
    rememberVerifyEmail(user.email, true);
    router.push("/auth/verify-email");
    return;
  }
  if (user.onboarding_completed) {
    await hydrateStoredProfile(user.role);
    router.push(homeFor(user.role));
    return;
  }
  router.push(onboardingFor(user.role));
}

function Header({
  kicker,
  title,
  intro,
}: {
  kicker: string;
  title: React.ReactNode;
  intro: React.ReactNode;
}) {
  return (
    <div className="auth-heading">
      <p className="auth-kicker">
        <span>✳</span> {kicker}
      </p>
      <h1>{title}</h1>
      <p className="auth-intro">{intro}</p>
    </div>
  );
}

function BackLink({
  href,
  children,
}: {
  href: string;
  children: React.ReactNode;
}) {
  return (
    <Link className="back-link" href={href}>
      <Icon name="back" />
      {children}
    </Link>
  );
}

function ApiErrorMessage({ message }: { message: string }) {
  if (!message) return null;
  return (
    <p role="alert" className="field__error" style={{ marginBottom: "0.5rem" }}>
      {message}
    </p>
  );
}

export function SignUpChoice() {
  const router = useRouter();
  const { role, setRole } = useAuthFlow();
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const submittedRole = new FormData(event.currentTarget).get("role");
    const nextRole: AccountRole = submittedRole === "organisation" ? "organisation" : "creator";
    setRole(nextRole);
    router.push(
      nextRole === "organisation"
        ? "/auth/sign-up/organisation"
        : "/auth/sign-up/creator",
    );
  };
  return (
    <section className="auth-screen" aria-labelledby="signup-title">
      <Header
        kicker="Pick your side of the magic"
        title={
          <>
            How will you
            <br />
            use Clippit?
          </>
        }
        intro={
          <>
            Make content and earn from verified views, or fund the ideas you
            want the internet to see.
          </>
        }
      />
      <form id="roleForm" className="auth-form role-form" action="/auth/sign-up/continue" method="get" onSubmit={submit}>
        <fieldset>
          <legend className="sr-only">Choose an account type</legend>
          <RoleCard
            checked={role === "creator"}
            role="creator"
            title="I make the content."
            copy="Find briefs, post your way, earn in naira."
            onChange={setRole}
          />
          <RoleCard
            checked={role === "organisation"}
            role="organisation"
            title="I fund the content."
            copy="Launch campaigns and pay for verified attention."
            onChange={setRole}
          />
        </fieldset>
        <AuthButton>Continue</AuthButton>
      </form>
      <p className="auth-legal">
        By continuing, you agree to Clippit's <Link href="/terms">Terms</Link>{" "}
        and <Link href="/privacy">Privacy Policy</Link>.
      </p>
    </section>
  );
}

function RoleCard({
  checked,
  role,
  title,
  copy,
  onChange,
}: {
  checked: boolean;
  role: AccountRole;
  title: string;
  copy: string;
  onChange: (role: AccountRole) => void;
}) {
  const organisation = role === "organisation";
  return (
    <label className="role-card">
      <input
        type="radio"
        name="role"
        value={role}
        checked={checked}
        onChange={() => onChange(role)}
      />
      <span
        className={`role-card__icon${organisation ? " role-card__icon--gold" : ""}`}
      >
        <Icon name={organisation ? "building" : "user"} />
      </span>
      <span className="role-card__copy">
        <strong>{title}</strong>
        <small>{copy}</small>
      </span>
      <span className="role-card__radio" aria-hidden="true" />
    </label>
  );
}

export function SignUpDetails({ role }: { role: AccountRole }) {
  const router = useRouter();
  const flow = useAuthFlow();
  const [errors, setErrors] = useState<Errors>({});
  const [apiError, setApiError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [existing, setExisting] = useState<{ email: string; name: string } | null>(null);
  const organisation = role === "organisation";

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrors({});
    setApiError("");
    setExisting(null);

    const data = new FormData(event.currentTarget);
    const email = String(data.get("email") ?? "").trim();
    const password = String(data.get("password") ?? "");

    const next: Errors = {};
    if (!isEmail(email)) next.email = "Enter a valid email address.";
    if (!isStrongPassword(password))
      next.password = "Use 8+ characters with at least one number.";

    let full_name: string;
    if (organisation) {
      const org = String(data.get("organisation") ?? "").trim();
      if (!org) next.organisation = "Enter your organisation name.";
      full_name = org;
    } else {
      const firstName = String(data.get("firstName") ?? "").trim();
      const lastName = String(data.get("lastName") ?? "").trim();
      if (!firstName) next.firstName = "Enter your first name.";
      if (!lastName) next.lastName = "Enter your last name.";
      full_name = `${firstName} ${lastName}`.trim();
    }

    setErrors(next);
    if (Object.keys(next).length) return;

    setIsLoading(true);
    try {
      const result = await authApi.signup({ email, password, full_name, role });
      storeTokens(result);
      flow.setEmail(email);
      flow.setRole(result.user.role);
      flow.setCompletion("signup");
      rememberVerifyEmail(email);
      router.push("/auth/verify-email");
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 409) {
          setExisting({ email, name: full_name.split(/\s+/)[0] || "there" });
        } else {
          setApiError(err.detail);
        }
      } else {
        setApiError("Something went wrong. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <section className="auth-screen" aria-labelledby="details-title">
      <BackLink href="/auth/sign-up">Change account type</BackLink>
      <Header
        kicker={organisation ? "Organisation account" : "Creator account"}
        title={
          organisation ? (
            <>
              Bring the budget.
              <br />
              We'll bring the buzz.
            </>
          ) : (
            <>
              Your page.
              <br />
              Your payday.
            </>
          )
        }
        intro={
          organisation ? (
            <>
              For brands, artists, labels, podcasts, and anyone funding good
              creative work.
            </>
          ) : (
            <>
              No follower minimum. Use your real details so future payouts land
              cleanly.
            </>
          )
        }
      />
      <form
        id={organisation ? "brandForm" : "creatorForm"}
        className="auth-form"
        onSubmit={submit}
        noValidate
      >
        <GoogleAuthButton
          intent="signup"
          onClick={() => {
            window.location.href = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/auth/google/login?role=${role}`;
          }}
        />
        <AuthDivider />
        {organisation ? (
          <TextField
            label="Organisation name"
            name="organisation"
            autoComplete="organization"
            placeholder="Gbedu Records"
            icon="building"
            error={errors.organisation}
          />
        ) : (
          <div className="field-row">
            <TextField
              label="First name"
              name="firstName"
              autoComplete="given-name"
              placeholder="Tomi"
              error={errors.firstName}
            />
            <TextField
              label="Last name"
              name="lastName"
              autoComplete="family-name"
              placeholder="Adeyemi"
              error={errors.lastName}
            />
          </div>
        )}
        <TextField
          label={organisation ? "Work email" : "Email address"}
          name="email"
          type="email"
          autoComplete="email"
          placeholder={organisation ? "you@company.com" : "you@example.com"}
          icon="mail"
          error={errors.email}
        />
        <PasswordField
          label="Create a password"
          autoComplete="new-password"
          placeholder="At least 8 characters"
          hint="Use 8+ characters with a number."
          error={errors.password}
        />
        <ApiErrorMessage message={apiError} />
        {existing && (
          <div role="alert" className="auth-notice">
            <p>
              <strong>Hey {existing.name}, you already have an account.</strong>{" "}
              <span>{existing.email} is already registered with Clippit. Sign in to pick up where you left off. If you haven&apos;t confirmed your email yet, we&apos;ll send you a fresh code.</span>
            </p>
            <Link href={`/auth/sign-in?email=${encodeURIComponent(existing.email)}`}>
              Go to sign in <Icon name="arrow" />
            </Link>
          </div>
        )}
        <AuthButton loading={isLoading} loadingLabel="Creating your account">
          {`Create my ${organisation ? "organisation" : "creator"} account`}
        </AuthButton>
      </form>
      <p className="switch-line">
        Already have an account? <Link href="/auth/sign-in">Sign in</Link>
      </p>
    </section>
  );
}

export function SignIn() {
  const router = useRouter();
  const flow = useAuthFlow();
  const [errors, setErrors] = useState<Errors>({});
  const [apiError, setApiError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [prefill, setPrefill] = useState("");

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      const email = new URLSearchParams(window.location.search).get("email");
      if (email) setPrefill(email);
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrors({});
    setApiError("");

    const data = new FormData(event.currentTarget);
    const email = String(data.get("email") ?? "").trim();
    const password = String(data.get("password") ?? "");

    const next: Errors = {};
    if (!isEmail(email)) next.email = "Enter a valid email address.";
    if (!password) next.password = "Enter your password.";
    setErrors(next);
    if (Object.keys(next).length) return;

    setIsLoading(true);
    try {
      const result = await authApi.login({ email, password });
      storeTokens(result);
      flow.setEmail(email);
      flow.setRole(result.user.role);
      flow.setCompletion("signin");
      await routeAfterAuth(router, result.user);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 401) {
          setErrors({ email: " ", password: "Incorrect email or password." });
        } else {
          setApiError(err.detail);
        }
      } else {
        setApiError("Something went wrong. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <section className="auth-screen" aria-labelledby="signin-title">
      <Header
        kicker="Welcome back"
        title={
          <>
            Ready when
            <br />
            you are.
          </>
        }
        intro={
          <>
            Sign in to check the brief, the views, and the money in the middle.
          </>
        }
      />
      <form id="signinForm" className="auth-form" onSubmit={submit} noValidate>
        <GoogleAuthButton
          intent="signin"
          onClick={() => {
            window.location.href = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/auth/google/login`;
          }}
        />
        <AuthDivider />
        <TextField
          key={prefill}
          label="Email address"
          name="email"
          type="email"
          autoComplete="email"
          placeholder="you@example.com"
          icon="mail"
          defaultValue={prefill}
          error={errors.email}
        />
        <PasswordField
          label={
            <span className="field__label-line">
              Password{" "}
              <Link href="/auth/forgot-password">Forgot password?</Link>
            </span>
          }
          placeholder="Your password"
          error={errors.password}
        />
        <label className="check-field">
          <input type="checkbox" name="remember" />
          <span aria-hidden="true">
            <Icon name="check" />
          </span>
          Keep me signed in on this device
        </label>
        <ApiErrorMessage message={apiError} />
        <AuthButton loading={isLoading} loadingLabel="Opening your Clippit">
          Sign in to Clippit
        </AuthButton>
      </form>
      <p className="switch-line">
        New around here? <Link href="/auth/sign-up">Create an account</Link>
      </p>
    </section>
  );
}

export function ForgotPassword() {
  const router = useRouter();
  const flow = useAuthFlow();
  const [error, setError] = useState("");
  const [apiError, setApiError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    setApiError("");

    const email = String(new FormData(event.currentTarget).get("email") ?? "").trim();
    if (!isEmail(email)) return setError("Enter a valid email address.");

    setIsLoading(true);
    try {
      await authApi.forgotPassword({ email });
      flow.setEmail(email);
      rememberVerifyEmail(email);
      router.push("/auth/recovery-code");
    } catch (err) {
      if (err instanceof ApiError) {
        setApiError(err.detail);
      } else {
        setApiError("Something went wrong. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <section className="auth-screen" aria-labelledby="forgot-title">
      <BackLink href="/auth/sign-in">Back to sign in</BackLink>
      <div className="scribble-key" aria-hidden="true">
        *
      </div>
      <Header
        kicker="Password rescue"
        title={
          <>
            Let's get you
            <br />
            back in.
          </>
        }
        intro={
          <>
            Enter the email on your account. We'll send the code; you set the
            new password.
          </>
        }
      />
      <form id="forgotForm" className="auth-form" onSubmit={submit} noValidate>
        <TextField
          label="Email address"
          name="email"
          type="email"
          autoComplete="email"
          placeholder="you@example.com"
          icon="mail"
          error={error}
        />
        <ApiErrorMessage message={apiError} />
        <AuthButton loading={isLoading} loadingLabel="Sending your code">
          Send recovery code
        </AuthButton>
      </form>
    </section>
  );
}

export function OtpPage({ recovery = false }: { recovery?: boolean }) {
  const router = useRouter();
  const flow = useAuthFlow();
  const refs = useRef<Array<HTMLInputElement | null>>([]);
  const [digits, setDigits] = useState(["", "", "", "", "", ""]);
  const [error, setError] = useState("");
  const [apiError, setApiError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const [notice, setNotice] = useState("");
  const [storedEmail, setStoredEmail] = useState("");
  const [sending, setSending] = useState(false);
  const email = flow.email || storedEmail;

  useEffect(() => {
    if (!cooldown) return;
    const timer = window.setTimeout(() => setCooldown((value) => Math.max(0, value - 1)), 1000);
    return () => window.clearTimeout(timer);
  }, [cooldown]);

  const update = (index: number, value: string) => {
    const digit = value.replace(/\D/g, "").slice(-1);
    setDigits((current) =>
      current.map((item, itemIndex) => (itemIndex === index ? digit : item)),
    );
    if (digit && index < 5) refs.current[index + 1]?.focus();
    setError("");
  };

  const keyDown = (index: number, event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Backspace" && !digits[index] && index > 0)
      refs.current[index - 1]?.focus();
  };

  const paste = (event: ClipboardEvent<HTMLDivElement>) => {
    const incoming = event.clipboardData
      .getData("text")
      .replace(/\D/g, "")
      .slice(0, 6)
      .split("");
    if (!incoming.length) return;
    event.preventDefault();
    setDigits(Array.from({ length: 6 }, (_, index) => incoming[index] ?? ""));
    refs.current[Math.min(incoming.length, 6) - 1]?.focus();
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const code = digits.join("");
    if (code.length !== 6) return setError("Enter all six digits.");
    setError("");
    setApiError("");
    setIsLoading(true);

    try {
      if (recovery) {
        const result = await authApi.verifyRecoveryCode({ email, code });
        flow.setResetToken(result.reset_token);
        router.push("/auth/reset-password");
      } else {
        const user = await authApi.verifyEmail({ code, email: email || undefined });
        try { window.sessionStorage.removeItem(VERIFY_EMAIL_KEY); } catch { /* ignore */ }
        if (user.onboarding_completed) {
          await routeAfterAuth(router, user);
        } else {
          flow.setCompletion("signup");
          router.push("/auth/success");
        }
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setApiError("Something went wrong. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  const resend = async (target = email) => {
    if (cooldown || sending) return;
    setSending(true);
    setNotice("");
    setApiError("");
    try {
      const result = recovery
        ? await authApi.forgotPassword({ email: target })
        : await authApi.resendVerification({ email: target || undefined });
      setNotice(`We sent a new code to ${target || "your inbox"}. Check spam or promotions if you don't see it.`);
      setCooldown(result.resend_in || 60);
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        const wait = Number(/(\d+)\s*s/.exec(err.detail)?.[1] ?? 60);
        setNotice(`A code was sent recently. You can ask for another in ${wait}s — check your inbox for the last one.`);
        setCooldown(wait);
      } else if (err instanceof ApiError && err.status === 409) {
        setNotice("This email is already confirmed. Sign in to continue.");
      } else {
        setApiError(err instanceof ApiError ? err.detail : "We couldn't send a new code. Check your connection and try again.");
      }
    } finally {
      setSending(false);
    }
  };

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      let saved = "";
      let autosend = false;
      try {
        saved = window.sessionStorage.getItem(VERIFY_EMAIL_KEY) ?? "";
        autosend = !recovery && window.sessionStorage.getItem(VERIFY_AUTOSEND_KEY) === "1";
        window.sessionStorage.removeItem(VERIFY_AUTOSEND_KEY);
      } catch {
        // sessionStorage unavailable
      }
      if (saved) setStoredEmail(saved);
      if (autosend) void resend(flow.email || saved);
    });
    return () => window.cancelAnimationFrame(frame);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <section className="auth-screen" aria-labelledby="otp-title">
      <BackLink
        href={
          recovery
            ? "/auth/forgot-password"
            : flow.role === "organisation"
              ? "/auth/sign-up/organisation"
              : "/auth/sign-up/creator"
        }
      >
        {recovery ? "Use another email" : "Edit your details"}
      </BackLink>
      {!recovery && (
        <div className="mail-stamp" aria-hidden="true">
          <Icon name="mail" />
          <span>✳</span>
        </div>
      )}
      <Header
        kicker={recovery ? "Found you" : "One quick check"}
        title={
          recovery ? (
            <>
              Six digits.
              <br />
              Then you're in.
            </>
          ) : (
            <>
              Check your
              <br />
              inbox.
            </>
          )
        }
        intro={
          <>
            Enter the {recovery ? "recovery" : "verification"} code sent to{" "}
            <strong>{email || "your email"}</strong>.
          </>
        }
      />
      <form
        id={recovery ? "recoveryForm" : "verifyForm"}
        className="auth-form"
        onSubmit={submit}
      >
        <fieldset className="otp-group">
          <legend>
            Enter your {recovery ? "recovery" : "verification"} code
          </legend>
          <div className="otp-inputs" data-otp onPaste={paste}>
            {digits.map((digit, index) => (
              <input
                key={index}
                ref={(node) => {
                  refs.current[index] = node;
                }}
                aria-label={`Digit ${index + 1}`}
                inputMode="numeric"
                autoComplete={index === 0 ? "one-time-code" : "off"}
                maxLength={1}
                value={digit}
                onChange={(event) => update(index, event.target.value)}
                onKeyDown={(event) => keyDown(index, event)}
                required
              />
            ))}
          </div>
          <small className="otp-error" role="alert">
            {error}
          </small>
        </fieldset>
        <ApiErrorMessage message={apiError} />
        <AuthButton loading={isLoading} loadingLabel="Checking your code">
          {recovery ? "Check the code" : "Verify my email"}
        </AuthButton>
      </form>
      {notice && (
        <p role="status" className="auth-notice auth-notice--quiet">
          {notice}
        </p>
      )}
      <p className="resend-line">
        {recovery ? "Code taking its time?" : "Nothing yet?"}{" "}
        <button type="button" onClick={() => void resend()} disabled={Boolean(cooldown) || sending}>
          {sending ? "Sending…" : recovery ? "Send again" : "Send a new code"}
        </button>
        {cooldown ? (
          <span>
            {" "}
            {Math.floor(cooldown / 60)}:{String(cooldown % 60).padStart(2, "0")}
          </span>
        ) : null}
      </p>
    </section>
  );
}

export function ResetPassword() {
  const router = useRouter();
  const flow = useAuthFlow();
  const [errors, setErrors] = useState<Errors>({});
  const [apiError, setApiError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [password, setPassword] = useState("");

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrors({});
    setApiError("");

    const data = new FormData(event.currentTarget);
    const nextPassword = String(data.get("password") ?? "");
    const confirm = String(data.get("confirmPassword") ?? "");

    const next: Errors = {};
    if (!isStrongPassword(nextPassword))
      next.password = "Use 8+ characters with at least one number.";
    if (confirm !== nextPassword)
      next.confirmPassword = "Those passwords do not match.";
    setErrors(next);
    if (Object.keys(next).length) return;

    if (!flow.resetToken) {
      setApiError("Your reset session has expired. Start again.");
      return;
    }

    setIsLoading(true);
    try {
      await authApi.resetPassword({ reset_token: flow.resetToken, password: nextPassword });
      flow.setCompletion("recovery");
      router.push("/auth/success");
    } catch (err) {
      if (err instanceof ApiError) {
        setApiError(err.detail);
      } else {
        setApiError("Something went wrong. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <section className="auth-screen" aria-labelledby="reset-title">
      <BackLink href="/auth/recovery-code">Back to code</BackLink>
      <Header
        kicker="Fresh start"
        title={
          <>
            Make it strong.
            <br />
            Make it yours.
          </>
        }
        intro={<>Choose a password you haven't used on Clippit before.</>}
      />
      <form id="resetForm" className="auth-form" onSubmit={submit} noValidate>
        <div
          onInput={(event) => {
            const input = event.target as HTMLInputElement;
            if (input.name === "password") setPassword(input.value);
          }}
        >
          <PasswordField
            label="New password"
            name="password"
            autoComplete="new-password"
            placeholder="Your new password"
            error={errors.password}
          />
          <PasswordField
            label="Confirm password"
            name="confirmPassword"
            autoComplete="new-password"
            placeholder="Type it again"
            error={errors.confirmPassword}
          />
        </div>
        <ul className="password-rules">
          <li className={password.length >= 8 ? "is-met" : ""}>
            <span>
              <Icon name="check" />
            </span>
            8 or more characters
          </li>
          <li className={/\d/.test(password) ? "is-met" : ""}>
            <span>
              <Icon name="check" />
            </span>
            At least one number
          </li>
        </ul>
        <ApiErrorMessage message={apiError} />
        <AuthButton loading={isLoading} loadingLabel="Securing your password">
          Save my new password
        </AuthButton>
      </form>
    </section>
  );
}

export function Success() {
  const router = useRouter();
  const { completion, role } = useAuthFlow();
  const signin = completion === "signin";
  const recovery = completion === "recovery";

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const accessToken = params.get("access_token");
    const refreshToken = params.get("refresh_token");
    const next = params.get("next");
    if (accessToken) {
      storeTokens({ access_token: accessToken, refresh_token: refreshToken });
      window.history.replaceState({}, "", window.location.pathname);
      if (next) router.replace(next);
    }
  }, [router]);
  const copy = signin
    ? "You're signed in. Head to your dashboard to get started."
    : recovery
      ? "Your password is reset. You can sign in with the new one now."
      : role === "organisation"
        ? "Your organisation workspace is ready for its first funded brief."
        : "Your creator profile is ready for its first campaign.";
  return (
    <section className="auth-screen" aria-labelledby="success-title">
      <div className="mail-stamp" aria-hidden="true">
        <Icon name="check" />
        <span>✳</span>
      </div>
      <Header
        kicker="All sorted"
        title={
          <>
            You're in.
            <br />
            Make your move.
          </>
        }
        intro={copy}
      />
      <Link
        className="auth-button"
        href={
          recovery
            ? "/auth/sign-in"
            : role === "organisation"
              ? "/onboarding/brand"
              : "/onboarding/creator"
        }
      >
        {recovery
          ? "Sign in"
          : signin
            ? "Go to my dashboard"
            : "Set up my Clippit"}
        <Icon name="arrow" />
      </Link>
    </section>
  );
}
