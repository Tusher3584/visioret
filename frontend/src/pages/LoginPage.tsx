import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { LogoMark } from "../components/layout/LogoMark";
import { Button } from "../components/ui/Button";
import { useAuth } from "../context/AuthContext";

export function LoginPage() {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { login, register } = useAuth();
  const navigate = useNavigate();

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);
    try {
      if (mode === "login") await login(email, password);
      else await register(name, email, password);
      navigate("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-[380px] py-6">
      <div className="border border-line bg-surface rounded-[3px]">
        <div className="flex flex-col items-center gap-2.5 border-b border-line px-6 py-6 text-center">
          <LogoMark size={30} />
          <h1 className="text-sm font-semibold tracking-[0.14em] text-ink">VISIORET</h1>
          <p className="text-xs leading-relaxed text-muted">
            Signing in attributes the scans you analyse and the reviews you record to your account.
            Analysis works without an account.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-3 px-6 py-5">
          {mode === "register" && (
            <Field label="Name">
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                autoComplete="name"
                className={INPUT}
              />
            </Field>
          )}

          <Field label="Email">
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              className={INPUT}
            />
          </Field>

          <Field label="Password" hint={mode === "register" ? "At least 8 characters." : undefined}>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={mode === "register" ? 8 : undefined}
              autoComplete={mode === "register" ? "new-password" : "current-password"}
              className={INPUT}
            />
          </Field>

          {error && (
            <p role="alert" className="text-xs text-rose-700 dark:text-rose-300">
              {error}
            </p>
          )}

          <Button type="submit" variant="primary" disabled={isSubmitting} className="mt-1 w-full">
            {isSubmitting ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
          </Button>
        </form>

        <div className="border-t border-line px-6 py-3 text-center">
          <button
            onClick={() => {
              setMode(mode === "login" ? "register" : "login");
              setError(null);
            }}
            // min-h-6 for a 24px hit area (WCAG 2.2 2.5.8); it measured 16px.
            className="inline-flex min-h-6 items-center justify-center text-xs font-medium text-accent hover:underline"
          >
            {mode === "login" ? "Need an account? Register" : "Already registered? Sign in"}
          </button>
        </div>
      </div>
    </div>
  );
}

const INPUT =
  "rounded-[3px] border border-line-strong bg-surface px-2.5 py-2 text-sm text-ink placeholder:text-subtle";

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-xs font-medium text-ink">{label}</span>
      {children}
      {hint && <span className="text-[11px] text-subtle">{hint}</span>}
    </label>
  );
}
