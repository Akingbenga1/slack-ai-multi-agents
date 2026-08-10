import Link from "next/link";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";

export default async function Home() {
  const session = await getServerSession(authOptions);
  const shell =
    session?.user?.role === "platform_owner"
      ? "/admin"
      : session?.user?.role === "org_admin"
        ? "/app"
        : null;

  return (
    <main
      style={{
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        fontFamily: "system-ui, sans-serif",
        gap: "1rem",
        padding: "1.5rem",
      }}
    >
      <p
        style={{
          fontSize: "2rem",
          fontWeight: 600,
          letterSpacing: "0.05em",
          margin: 0,
        }}
      >
        OK
      </p>
      {session?.user ? (
        <>
          <p style={{ margin: 0, color: "#333" }}>
            Signed in as {session.user.email} ({session.user.role}
            {session.user.tenantId ? ` · tenant ${session.user.tenantId}` : ""})
          </p>
          <p style={{ margin: 0 }}>
            {shell ? <Link href={shell}>Open portal</Link> : null} ·{" "}
            <Link href="/invite">Invite rules</Link>
          </p>
        </>
      ) : (
        <p style={{ margin: 0 }}>
          <Link href="/login">Sign in</Link>
        </p>
      )}
    </main>
  );
}
