import Link from "next/link";
import { PRODUCT_MARK, PRODUCT_NAME } from "@/lib/brand";
import { cn } from "@/lib/utils";

type Props = {
  href?: string;
  showSubtitle?: boolean;
  className?: string;
};

export function PublicBrand({ href = "/", showSubtitle = true, className }: Props) {
  const content = (
    <>
      <span className="flex h-11 w-11 items-center justify-center rounded-lg bg-primary text-sm font-bold tracking-wide text-primary-foreground">
        {PRODUCT_MARK}
      </span>
      <span className="text-left">
        <span className="block text-base font-semibold text-foreground">{PRODUCT_NAME}</span>
        {showSubtitle ? (
          <span className="block text-sm text-muted-foreground">Organisation portal</span>
        ) : null}
      </span>
    </>
  );

  const classNames = cn("inline-flex items-center gap-3", className);

  if (href) {
    return (
      <Link href={href} className={cn(classNames, "hover:opacity-90")}>
        {content}
      </Link>
    );
  }

  return <div className={classNames}>{content}</div>;
}
