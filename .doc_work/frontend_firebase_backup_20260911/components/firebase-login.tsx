"use client";

import { useState } from "react";
import { sendPasswordResetEmail, signInWithEmailAndPassword, signOut } from "firebase/auth";

import { getFirebaseAuthentication } from "@/services/firebase-client";

function failureMessage(error: unknown): string {
  const code = typeof error === "object" && error !== null ? Reflect.get(error, "code") : null;
  if (code === "auth/invalid-credential" || code === "auth/invalid-email" || code === "auth/user-disabled") {
    return "Firebase rejected the email or password.";
  }
  if (code === "auth/too-many-requests") return "Too many attempts. Please wait before trying again.";
  if (code === "auth/network-request-failed") return "Authentication is temporarily unavailable.";
  return "Sign-in could not be completed. Please try again.";
}

export function FirebaseLogin(): React.ReactNode {
  const [mode, setMode] = useState<"sign-in" | "forgot-password">("sign-in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  async function establishSession(idToken: string): Promise<void> {
    const response = await fetch("/api/auth/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ idToken }),
    });
    if (!response.ok) {
      setBusy(false);
      setError(response.status === 403 ? "Your account does not have dashboard access." : "Authentication could not be verified.");
      return;
    }
    window.location.reload();
  }

  async function signIn(event: React.FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const auth = await getFirebaseAuthentication();
      const credential = await signInWithEmailAndPassword(auth, email.trim(), password);
      const idToken = await credential.user.getIdToken();
      await signOut(auth);
      await establishSession(idToken);
    } catch (authenticationError: unknown) {
      setBusy(false);
      setError(failureMessage(authenticationError));
    }
  }

  async function resetPassword(event: React.FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const auth = await getFirebaseAuthentication();
      await sendPasswordResetEmail(auth, email.trim());
      setMode("sign-in");
      setNotice("Password reset email sent. Follow the link, then sign in with your new password.");
    } catch (resetError: unknown) {
      setError(failureMessage(resetError));
    } finally {
      setBusy(false);
    }
  }

  if (mode === "forgot-password") {
    return <form className="auth-form" onSubmit={(event) => { void resetPassword(event); }}>
      <p className="auth-help">Enter the email address linked to your Firebase account.</p>
      <label htmlFor="reset-email">Email</label>
      <input id="reset-email" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required maxLength={320} />
      {error && <p className="auth-error" role="alert">{error}</p>}
      <button className="button primary auth-button" type="submit" disabled={busy}>{busy ? "Sending…" : "Send reset email"}</button>
      <button className="auth-link" type="button" disabled={busy} onClick={() => { setMode("sign-in"); setError(""); }}>Back to sign in</button>
    </form>;
  }

  return <form className="auth-form" onSubmit={(event) => { void signIn(event); }}>
    <label htmlFor="firebase-email">Email</label>
    <input id="firebase-email" type="email" autoComplete="username" value={email} onChange={(event) => setEmail(event.target.value)} required maxLength={320} />
    <label htmlFor="firebase-password">Password</label>
    <input id="firebase-password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required maxLength={256} />
    <button className="auth-link auth-forgot" type="button" disabled={busy} onClick={() => { setMode("forgot-password"); setError(""); setNotice(""); }}>Forgot password?</button>
    {notice && <p className="auth-success" role="status">{notice}</p>}
    {error && <p className="auth-error" role="alert">{error}</p>}
    <button className="button primary auth-button" type="submit" disabled={busy}>{busy ? "Signing in…" : "Sign in securely"}</button>
  </form>;
}
