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

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("owner@example.com");
  const [password, setPassword] = useState("owner123");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setPending(true);
    setError(null);
    const result = await signIn("credentials", {
      email,
      password,
      redirect: false,
    });
    setPending(false);
    if (result?.error) {
      setError("Invalid email or password");
      return;
    }
    const dest = email.toLowerCase().startsWith("owner@") ? "/admin" : "/app";
    router.push(dest);
    router.refresh();
  }

  return (
    <PublicAuthShell
      title="Sign in"
      description="Demo: owner@example.com / owner123 → admin · admin@example.com / admin123 → org portal"
      footer={
        <>
          New organisation?{" "}
          <Link href="/signup" className="font-medium text-primary hover:underline">
            Create an organisation
          </Link>
        </>
      }
    >
      <form onSubmit={(ev) => void onSubmit(ev)} className="space-y-4">
        <AuthFormField label="Email">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
            className={authInputClassName}
          />
        </AuthFormField>
        <AuthFormField label="Password">
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="current-password"
            className={authInputClassName}
          />
        </AuthFormField>
        {error ? (
          <p className="text-sm text-danger" role="alert">
            {error}
          </p>
        ) : null}
        <Button type="submit" disabled={pending} className="w-full rounded-full">
          {pending ? "Signing in…" : "Sign in"}
        </Button>
      </form>
    </PublicAuthShell>
  );
}
