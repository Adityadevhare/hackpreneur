import { useState } from "react";
import type { FormEvent } from "react";

import { useAuth } from "./auth-context";

type AuthMode = "signin" | "signup";

function AuthScreen() {
  const { signIn, signUp, error, clearError } = useAuth();
  const [mode, setMode] = useState<AuthMode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [confirmationMessage, setConfirmationMessage] = useState<string | null>(
    null,
  );

  const isSignUp = mode === "signup";
  const displayedError = formError ?? error;

  const switchMode = () => {
    setMode(isSignUp ? "signin" : "signup");
    setPassword("");
    setConfirmPassword("");
    setFormError(null);
    setConfirmationMessage(null);
    clearError();
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);
    setConfirmationMessage(null);
    clearError();

    const normalizedEmail = email.trim();

    if (!normalizedEmail || !password) {
      setFormError("Enter your email and password.");
      return;
    }

    if (isSignUp && password !== confirmPassword) {
      setFormError("Passwords do not match.");
      return;
    }

    setSubmitting(true);

    try {
      if (!isSignUp) {
        await signIn(normalizedEmail, password);
        return;
      }

      const result = await signUp(normalizedEmail, password);

      if (!result) {
        return;
      }

      if (result.requiresEmailConfirmation) {
        setConfirmationMessage(
          "Check your email to confirm your account before signing in.",
        );
      } else {
        setConfirmationMessage("Your account is ready.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="app">
      <main
        className="main-content"
        style={{
          width: "100%",
          minHeight: "100vh",
          display: "grid",
          placeItems: "center",
          padding: "24px",
        }}
      >
        <section className="panel" style={{ width: "100%", maxWidth: 420 }}>
          <div className="brand" style={{ marginBottom: 28 }}>
            <div className="brand-icon">H</div>

            <div>
              <h2>HACKPRENEUR</h2>
              <span>Project Continuity Platform</span>
            </div>
          </div>

          <div
            className="panel-heading"
            style={{ display: "block", marginBottom: 20 }}
          >
            <h3
              style={{
                margin: 0,
                color: "var(--text-primary)",
                fontSize: 18,
                fontWeight: 720,
              }}
            >
              {isSignUp ? "Create your account" : "Welcome back"}
            </h3>

            <p
              style={{
                margin: "8px 0 0",
                color: "var(--text-secondary)",
                fontSize: 12,
                lineHeight: 1.6,
              }}
            >
              {isSignUp
                ? "Start building the next chapter of your project."
                : "Sign in to continue to your workspace."}
            </p>
          </div>

          <form className="project-form" onSubmit={handleSubmit} noValidate>
            <div className="form-group">
              <label htmlFor="auth-email">Email</label>

              <input
                id="auth-email"
                name="email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="you@example.com"
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="auth-password">Password</label>

              <input
                id="auth-password"
                name="password"
                type="password"
                autoComplete={isSignUp ? "new-password" : "current-password"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Enter your password"
                required
              />
            </div>

            {isSignUp && (
              <div className="form-group">
                <label htmlFor="auth-confirm-password">
                  Confirm password
                </label>

                <input
                  id="auth-confirm-password"
                  name="confirm-password"
                  type="password"
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  placeholder="Confirm your password"
                  required
                />
              </div>
            )}

            {displayedError && (
              <p className="form-error" role="alert">
                {displayedError}
              </p>
            )}

            {confirmationMessage && (
              <p
                role="status"
                style={{
                  margin: 0,
                  padding: "10px 12px",
                  border: "1px solid rgba(16, 185, 129, 0.25)",
                  borderRadius: "var(--radius-sm)",
                  background: "var(--success-subtle)",
                  color: "#A7F3D0",
                  fontSize: 11,
                  lineHeight: 1.5,
                }}
              >
                {confirmationMessage}
              </p>
            )}

            <div className="form-actions" style={{ paddingTop: 7 }}>
              <button
                type="submit"
                className="primary-button"
                disabled={submitting}
                style={{ width: "100%" }}
              >
                {submitting
                  ? "Please wait..."
                  : isSignUp
                    ? "Create account"
                    : "Sign in"}
              </button>
            </div>
          </form>

          <button
            type="button"
            className="secondary-button"
            onClick={switchMode}
            disabled={submitting}
            style={{ width: "100%", marginTop: 12 }}
          >
            {isSignUp
              ? "Already have an account? Sign in"
              : "Need an account? Sign up"}
          </button>
        </section>
      </main>
    </div>
  );
}

export default AuthScreen;
