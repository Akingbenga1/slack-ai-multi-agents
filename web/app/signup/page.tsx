"use client";

import { FormEvent, useState } from "react";
import { signIn } from "next-auth/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  AuthFormField,
  PublicAuthShell,
  authInputClassName,
} from "@/components/auth/PublicAuthShell";
import { Button } from "@/components/ui/button";

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
    <PublicAuthShell
      title="Create organisation"
      description="Register your organisation and the admin account that will manage it."
      maxWidth="lg"
      footer={
        <>
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-primary hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={(ev) => void onSubmit(ev)} className="space-y-4">
        <AuthFormField label="Organisation name">
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            maxLength={255}
            className={authInputClassName}
          />
        </AuthFormField>
        <AuthFormField label="Organisation URL" hint="Optional short name for links — generated from the organisation name if left blank">
          <input
            type="text"
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
            placeholder="acme-corp"
            maxLength={64}
            className={authInputClassName}
          />
        </AuthFormField>
        <AuthFormField label="Your email">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
            className={authInputClassName}
          />
        </AuthFormField>
        <AuthFormField label="Display name" hint="Optional">
          <input
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            maxLength={255}
            className={authInputClassName}
          />
        </AuthFormField>
        <AuthFormField label="Password" hint="Minimum 8 characters">
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            autoComplete="new-password"
            className={authInputClassName}
          />
        </AuthFormField>
        {error ? (
          <p className="text-sm text-danger" role="alert">
            {error}
          </p>
        ) : null}
        <Button type="submit" disabled={pending} className="w-full rounded-full">
          {pending ? "Creating…" : "Create organisation"}
        </Button>
      </form>
    </PublicAuthShell>
  );
}
