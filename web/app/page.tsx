import Link from "next/link";
import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";

export default async function Home() {
  const session = await getServerSession(authOptions);

  if (session?.user?.role === "platform_owner") {
    redirect("/admin");
  }
  if (session?.user?.role === "org_admin") {
    redirect("/app");
  }

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
      <p style={{ margin: 0 }}>
        <Link href="/login">Sign in</Link>
        {" · "}
        <Link href="/signup">Create organisation</Link>
      </p>
    </main>
  );
}
