import Link from "next/link";

export default function InvitePage() {
  return (
    <main
      style={{
        padding: "2rem",
        fontFamily: "system-ui, sans-serif",
        maxWidth: 640,
      }}
    >
      <h1 style={{ marginTop: 0 }}>Invite / membership</h1>
      <p>
        MVP rule: an <strong>org_admin</strong> belongs to exactly one tenant.
        A <strong>platform_owner</strong> has all-access and no tenant
        membership row.
      </p>
      <p>
        Demo seed: org admin{" "}
        <code>admin@example.com</code> → tenant{" "}
        <code>11111111-1111-1111-1111-111111111111</code> (demo-org). Invites
        that would attach a second tenant are rejected by the API membership
        helpers (single-tenant constraint).
      </p>
      <p style={{ color: "#555" }}>
        Full invite email/token flow comes later — this page documents the
        wiring for Sprint 3.
      </p>
      <p>
        <Link href="/app">Back to org portal</Link> · <Link href="/login">Login</Link>
      </p>
    </main>
  );
}
