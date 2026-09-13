"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
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

type Errors = Record<string, string>;

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
    <>
      <p className="auth-kicker">
        <span>✳</span> {kicker}
      </p>
      <h1>{title}</h1>
      <p className="auth-intro">{intro}</p>
    </>
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

export function SignUpChoice() {
  const router = useRouter();
  const { role, setRole } = useAuthFlow();
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    router.push(
      role === "organisation"
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
      <form id="roleForm" className="auth-form role-form" onSubmit={submit}>
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
        By continuing, you agree to Clippit’s <Link href="/terms">Terms</Link>{" "}
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
  const organisation = role === "organisation";
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const email = String(data.get("email") ?? "");
    const password = String(data.get("password") ?? "");
    const next: Errors = {};
    if (organisation && !String(data.get("organisation") ?? "").trim())
      next.organisation = "Enter your organisation name.";
    if (!organisation && !String(data.get("firstName") ?? "").trim())
      next.firstName = "Enter your first name.";
    if (!organisation && !String(data.get("lastName") ?? "").trim())
      next.lastName = "Enter your last name.";
    if (!isEmail(email)) next.email = "Enter a valid email address.";
    if (!isStrongPassword(password))
      next.password = "Use 8+ characters with at least one number.";
    setErrors(next);
    if (Object.keys(next).length) return;
    flow.setEmail(email.trim());
    flow.setRole(role);
    flow.setCompletion("signup");
    router.push("/auth/verify-email");
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
              We’ll bring the buzz.
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
        <GoogleAuthButton intent="signup" />
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
        <AuthButton>
          Create my {organisation ? "organisation" : "creator"} account
        </AuthButton>
      </form>
    </section>
  );
}

export function SignIn() {
  const router = useRouter();
  const flow = useAuthFlow();
  const [errors, setErrors] = useState<Errors>({});
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const email = String(data.get("email") ?? "");
    const password = String(data.get("password") ?? "");
    const next: Errors = {};
    if (!isEmail(email)) next.email = "Enter a valid email address.";
    if (!password) next.password = "Enter your password.";
    setErrors(next);
    if (Object.keys(next).length) return;
    flow.setEmail(email.trim());
    flow.setCompletion("signin");
    router.push("/auth/success");
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
        <GoogleAuthButton intent="signin" />
        <AuthDivider />
        <TextField
          label="Email address"
          name="email"
          type="email"
          autoComplete="email"
          placeholder="you@example.com"
          icon="mail"
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
        <AuthButton>Sign in to Clippit</AuthButton>
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
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const email = String(new FormData(event.currentTarget).get("email") ?? "");
    if (!isEmail(email)) return setError("Enter a valid email address.");
    flow.setEmail(email.trim());
    router.push("/auth/recovery-code");
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
            Let’s get you
            <br />
            back in.
          </>
        }
        intro={
          <>
            Enter the email on your account. We’ll send the code; you set the
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
        <AuthButton>Send recovery code</AuthButton>
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
  const [cooldown, setCooldown] = useState(0);
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
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (digits.join("").length !== 6) return setError("Enter all six digits.");
    if (recovery) router.push("/auth/reset-password");
    else {
      flow.setCompletion("signup");
      router.push("/auth/success");
    }
  };
  const resend = () => {
    if (cooldown) return;
    setCooldown(30);
    const timer = window.setInterval(
      () =>
        setCooldown((value) => {
          if (value <= 1) {
            window.clearInterval(timer);
            return 0;
          }
          return value - 1;
        }),
      1000,
    );
  };
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
              Then you’re in.
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
            <strong>{flow.email || "you@example.com"}</strong>.
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
        <AuthButton>
          {recovery ? "Check the code" : "Verify my email"}
        </AuthButton>
      </form>
      <p className="resend-line">
        {recovery ? "Code taking its time?" : "Nothing yet?"}{" "}
        <button type="button" onClick={resend} disabled={Boolean(cooldown)}>
          {recovery ? "Send again" : "Send a new code"}
        </button>
        {cooldown ? <span> 0:{String(cooldown).padStart(2, "0")}</span> : null}
      </p>
    </section>
  );
}

export function ResetPassword() {
  const router = useRouter();
  const flow = useAuthFlow();
  const [errors, setErrors] = useState<Errors>({});
  const [password, setPassword] = useState("");
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
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
    flow.setCompletion("recovery");
    router.push("/auth/success");
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
        intro={<>Choose a password you haven’t used on Clippit before.</>}
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
        <AuthButton>Save my new password</AuthButton>
      </form>
    </section>
  );
}

export function Success() {
  const { completion, role } = useAuthFlow();
  const signin = completion === "signin";
  const recovery = completion === "recovery";
  const copy = signin
    ? "You’re signed in. Your campaigns and earnings are ready when the product API lands."
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
            You’re in.
            <br />
            Make your move.
          </>
        }
        intro={copy}
      />
      <Link
        className="auth-button"
        href={recovery ? "/auth/sign-in" : "/#campaigns"}
      >
        {recovery ? "Sign in" : "Explore campaigns"}
        <Icon name="arrow" />
      </Link>
    </section>
  );
}
