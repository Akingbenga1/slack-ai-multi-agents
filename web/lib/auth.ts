import type { NextAuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";

export type AppRole = "platform_owner" | "org_admin";

type ApiMe = {
  sub: string;
  email: string;
  role: AppRole;
  tenant_id: string | null;
};

function apiBaseUrl(): string | null {
  const raw = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (!raw) return null;
  return raw.replace(/\/$/, "");
}

/** Mint FastAPI Bearer JWT (credentials validated server-side in Postgres). */
async function fetchApiAccessToken(
  email: string,
  password: string,
): Promise<string | null> {
  const base = apiBaseUrl();
  if (!base) return null;
  try {
    const res = await fetch(`${base}/auth/token`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) return null;
    const data = (await res.json()) as { access_token?: string };
    return data.access_token ?? null;
  } catch {
    return null;
  }
}

async function fetchApiMe(accessToken: string): Promise<ApiMe | null> {
  const base = apiBaseUrl();
  if (!base) return null;
  try {
    const res = await fetch(`${base}/auth/me`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    if (!res.ok) return null;
    return (await res.json()) as ApiMe;
  } catch {
    return null;
  }
}

export const authOptions: NextAuthOptions = {
  session: { strategy: "jwt" },
  pages: {
    signIn: "/login",
  },
  providers: [
    CredentialsProvider({
      name: "Credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials.password) {
          return null;
        }
        const accessToken = await fetchApiAccessToken(
          credentials.email,
          credentials.password,
        );
        if (!accessToken) {
          return null;
        }
        const me = await fetchApiMe(accessToken);
        if (!me?.sub || !me.email) {
          return null;
        }
        return {
          id: me.sub,
          email: me.email,
          name: me.email,
          role: me.role,
          tenantId: me.tenant_id,
          accessToken,
        };
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        const u = user as {
          role?: AppRole;
          tenantId?: string | null;
          accessToken?: string | null;
        };
        token.role = u.role;
        token.tenantId = u.tenantId ?? null;
        token.accessToken = u.accessToken ?? null;
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        session.user.id = token.sub ?? "";
        session.user.role = (token.role as AppRole) ?? "org_admin";
        session.user.tenantId = (token.tenantId as string | null) ?? null;
      }
      session.accessToken = (token.accessToken as string | null) ?? null;
      return session;
    },
  },
  secret: process.env.NEXTAUTH_SECRET,
};
