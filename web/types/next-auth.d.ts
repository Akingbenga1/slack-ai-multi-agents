import "next-auth";
import type { AppRole } from "@/lib/auth";

declare module "next-auth" {
  interface Session {
    accessToken?: string | null;
    user: {
      id: string;
      name?: string | null;
      email?: string | null;
      image?: string | null;
      role: AppRole;
      tenantId: string | null;
    };
  }

  interface User {
    role: AppRole;
    tenantId: string | null;
    accessToken?: string | null;
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    role?: AppRole;
    tenantId?: string | null;
    accessToken?: string | null;
  }
}
