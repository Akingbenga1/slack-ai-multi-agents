import Link from "next/link";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { PublicBrand } from "@/components/auth/PublicBrand";
import { cn } from "@/lib/utils";

export const authInputClassName =
  "w-full rounded-lg border border-border bg-card px-3 py-2 text-body-md text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-primary/20";

type Props = {
  title: string;
  description?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  maxWidth?: "md" | "lg";
};

export function PublicAuthShell({
  title,
  description,
  children,
  footer,
  maxWidth = "md",
}: Props) {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-[#f8fafc] px-4 py-12">
      <div className="mb-8">
        <PublicBrand />
      </div>
      <Card className={cn("w-full", maxWidth === "lg" ? "max-w-lg" : "max-w-md")}>
        <CardHeader className="border-b border-border">
          <div className="min-w-0">
            <CardTitle className="text-headline-md">{title}</CardTitle>
            {description ? (
              <CardDescription className="mt-2 max-w-prose">{description}</CardDescription>
            ) : null}
          </div>
        </CardHeader>
        <CardContent className="pt-6">{children}</CardContent>
      </Card>
      {footer ? (
        <div className="mt-6 max-w-md text-center text-sm text-muted-foreground">{footer}</div>
      ) : null}
    </main>
  );
}

export function AuthFormField({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-foreground">{label}</span>
      {hint ? (
        <span className="mt-1 block text-sm text-muted-foreground">{hint}</span>
      ) : null}
      <div className="mt-2">{children}</div>
    </label>
  );
}

export function PublicAuthFooterLink({
  href,
  children,
}: {
  href: string;
  children: React.ReactNode;
}) {
  return (
    <Link href={href} className="font-medium text-primary hover:underline">
      {children}
    </Link>
  );
}
