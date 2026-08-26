"use client";

import { FormEvent, useState } from "react";
import { signIn } from "next-auth/react";
import Link from "next/link";
import { useRouter } from "next/navigation";

function apiBaseUrl(): string | null {
  const raw = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (!raw) return null;
  return raw.replace(/\/$/, "");
}

function detailMessage(body: unknown, fallback: string): string {
  if (typeof body === "object" && body !== null && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail[0] && typeof detail[0] === "object") {
      const first = detail[0] as { msg?: string };
      if (first.msg) return first.msg;
    }
  }
  return fallback;
}

export default function SignupPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const base = apiBaseUrl();
    if (!base) {
      setError("NEXT_PUBLIC_API_BASE_URL is not set");
      return;
    }
    setPending(true);
    setError(null);
    try {
      const payload: Record<string, string> = {
        name: name.trim(),
        email: email.trim().toLowerCase(),
        password,
      };
      if (slug.trim()) payload.slug = slug.trim().toLowerCase();
      if (displayName.trim()) payload.display_name = displayName.trim();

      const res = await fetch(`${base}/auth/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = (await res.json().catch(() => null)) as unknown;
      if (!res.ok) {
        setError(detailMessage(body, "Could not create organisation"));
        return;
      }

      const result = await signIn("credentials", {
        email: email.trim().toLowerCase(),
        password,
        redirect: false,
      });
      if (result?.error) {
        setError("Account created, but sign-in failed. Try /login.");
        return;
      }
      router.push("/app");
      router.refresh();
    } catch {
      setError("Could not reach the API");
    } finally {
      setPending(false);
    }
  }

  return (
    <main
      style={{
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        fontFamily: "system-ui, sans-serif",
        padding: "1.5rem",
      }}
    >
      <form
        onSubmit={(ev) => void onSubmit(ev)}
        style={{
          width: "100%",
          maxWidth: 360,
          display: "grid",
          gap: "0.75rem",
        }}
      >
        <h1 style={{ margin: 0, fontSize: "1.5rem" }}>Create organisation</h1>
        <p style={{ margin: 0, color: "var(--muted)", fontSize: "0.9rem" }}>
          Register your org and admin account — no platform-owner ticket. You
          will land in the org portal. Paying, Slack, and agent setup stay
          self-serve after signup.
        </p>
        <label style={{ display: "grid", gap: 4 }}>
          <span>Organisation name</span>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            maxLength={255}
            style={{ padding: "0.5rem" }}
          />
        </label>
        <label style={{ display: "grid", gap: 4 }}>
          <span>Slug (optional)</span>
          <input
            type="text"
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
            placeholder="derived from name if blank"
            maxLength={64}
            style={{ padding: "0.5rem" }}
          />
        </label>
        <label style={{ display: "grid", gap: 4 }}>
          <span>Your email</span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
            style={{ padding: "0.5rem" }}
          />
        </label>
        <label style={{ display: "grid", gap: 4 }}>
          <span>Display name (optional)</span>
          <input
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            maxLength={255}
            style={{ padding: "0.5rem" }}
          />
        </label>
        <label style={{ display: "grid", gap: 4 }}>
          <span>Password</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            autoComplete="new-password"
            style={{ padding: "0.5rem" }}
          />
        </label>
        {error ? (
          <p style={{ color: "var(--error)", margin: 0 }} role="alert">
            {error}
          </p>
        ) : null}
        <button type="submit" disabled={pending} style={{ padding: "0.6rem" }}>
          {pending ? "Creating…" : "Create organisation"}
        </button>
        <p style={{ margin: 0, fontSize: "0.9rem" }}>
          Already have an account? <Link href="/login">Sign in</Link>
        </p>
      </form>
    </main>
  );
}
