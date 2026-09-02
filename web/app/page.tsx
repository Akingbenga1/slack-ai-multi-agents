import Link from "next/link";
import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { PublicBrand } from "@/components/auth/PublicBrand";
import { buttonVariants } from "@/components/ui/button";
import { PRODUCT_TAGLINE } from "@/lib/brand";
import { cn } from "@/lib/utils";

export default async function Home() {
  const session = await getServerSession(authOptions);

  if (session?.user?.role === "platform_owner") {
    redirect("/admin");
  }
  if (session?.user?.role === "org_admin") {
    redirect("/app");
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-[#f8fafc] px-4 py-16">
      <div className="w-full max-w-xl text-center">
        <div className="mb-8 flex justify-center">
          <PublicBrand href="/" showSubtitle={false} />
        </div>
        <p className="text-body-md text-muted-foreground sm:text-lg">{PRODUCT_TAGLINE}</p>
        <p className="mt-3 text-sm text-muted-foreground">
          Sign in to manage your organisation, or register a new one to get started.
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Link
            href="/login"
            className={cn(buttonVariants({ variant: "default" }), "rounded-full px-6")}
          >
            Sign in
          </Link>
          <Link
            href="/signup"
            className={cn(buttonVariants({ variant: "secondary" }), "rounded-full px-6")}
          >
            Create organisation
          </Link>
        </div>
      </div>
    </main>
  );
}
