import type { NextAuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";

export type AppRole = "platform_owner" | "org_admin";

type DemoUser = {
  id: string;
  email: string;
  password: string;
  name: string;
  role: AppRole;
  tenantId: string | null;
};

/** Demo users only — replace with DB in later auth tasks. */
const DEMO_USERS: DemoUser[] = [
  {
    id: "user-platform-owner",
    email: "owner@example.com",
    password: "owner123",
    name: "Platform Owner",
    role: "platform_owner",
    tenantId: null,
  },
  {
    id: "user-org-admin",
    email: "admin@example.com",
    password: "admin123",
    name: "Org Admin",
    role: "org_admin",
    tenantId: "11111111-1111-1111-1111-111111111111",
  },
];

function apiBaseUrl(): string | null {
  const raw = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (!raw) return null;
  return raw.replace(/\/$/, "");
}

/** Mint FastAPI Bearer JWT with the same demo credentials (architecture: session → API). */
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
        const user = DEMO_USERS.find(
          (u) =>
            u.email.toLowerCase() === credentials.email.toLowerCase() &&
            u.password === credentials.password,
        );
        if (!user) {
          return null;
        }
        const accessToken = await fetchApiAccessToken(
          credentials.email,
          credentials.password,
        );
        return {
          id: user.id,
          email: user.email,
          name: user.name,
          role: user.role,
          tenantId: user.tenantId,
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
