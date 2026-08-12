"use client";

import { FormEvent, useState } from "react";
import { signIn } from "next-auth/react";
import Link from "next/link";
import { useRouter } from "next/navigation";

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
    // Role-based shell: owner → /admin, org → /app
    const dest = email.toLowerCase().startsWith("owner@") ? "/admin" : "/app";
    router.push(dest);
    router.refresh();
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
        onSubmit={onSubmit}
        style={{
          width: "100%",
          maxWidth: 360,
          display: "grid",
          gap: "0.75rem",
        }}
      >
        <h1 style={{ margin: 0, fontSize: "1.5rem" }}>Sign in</h1>
        <p style={{ margin: 0, color: "#555", fontSize: "0.9rem" }}>
          Demo: owner@example.com / owner123 → /admin · admin@example.com /
          admin123 → /app
        </p>
        <label style={{ display: "grid", gap: 4 }}>
          <span>Email</span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
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
            style={{ padding: "0.5rem" }}
          />
        </label>
        {error ? (
          <p style={{ color: "#b00020", margin: 0 }} role="alert">
            {error}
          </p>
        ) : null}
        <button type="submit" disabled={pending} style={{ padding: "0.6rem" }}>
          {pending ? "Signing in…" : "Sign in"}
        </button>
        <p style={{ margin: 0, fontSize: "0.9rem" }}>
          New organisation? <Link href="/signup">Create an account</Link>
        </p>
      </form>
    </main>
  );
}
