"use client";

import Link from "next/link";
import { useEffect, useId, useRef } from "react";
import { IconMoreVertical } from "@/components/dashboard/icons";
import { cn } from "@/lib/utils";

type Props = {
  tenantId: string;
  label: string;
  open: boolean;
  disabled?: boolean;
  onOpenChange: (open: boolean) => void;
  canDeactivate: boolean;
  canWaive: boolean;
  tenantActive: boolean;
  onDeactivatePlan: () => void;
  onWaivePayment: () => void;
  onToggleSuspend: () => void;
};

export function TenantRowMenu({
  tenantId,
  label,
  open,
  disabled,
  onOpenChange,
  canDeactivate,
  canWaive,
  tenantActive,
  onDeactivatePlan,
  onWaivePayment,
  onToggleSuspend,
}: Props) {
  const menuId = useId();
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;

    function onPointerDown(ev: MouseEvent) {
      if (!rootRef.current?.contains(ev.target as Node)) {
        onOpenChange(false);
      }
    }

    function onKeyDown(ev: KeyboardEvent) {
      if (ev.key === "Escape") {
        onOpenChange(false);
      }
    }

    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open, onOpenChange]);

  function run(action: () => void) {
    onOpenChange(false);
    action();
  }

  const hasBilling = canDeactivate || canWaive;

  const menuItemClass =
    "block w-full rounded-md px-3 py-2 text-left text-sm text-foreground hover:bg-muted";

  return (
    <div ref={rootRef} className="relative flex justify-end">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
        aria-label={`Actions for ${label}`}
        disabled={disabled}
        onClick={() => onOpenChange(!open)}
        className="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-muted disabled:opacity-50"
      >
        <IconMoreVertical size={18} />
      </button>

      {open ? (
        <div
          id={menuId}
          role="menu"
          className="absolute top-full right-0 z-20 mt-1 min-w-[12rem] rounded-lg border border-border bg-card py-1 shadow-[0_10px_25px_-5px_rgba(0,0,0,0.05)]"
        >
          <p role="presentation" className="px-3 py-1.5 text-label-md text-muted-foreground">
            Records
          </p>
          <Link
            href={`/admin/tenants/${tenantId}/billing`}
            role="menuitem"
            className={menuItemClass}
            onClick={() => onOpenChange(false)}
          >
            View billing
          </Link>
          <Link
            href={`/admin/tenants/${tenantId}/tools`}
            role="menuitem"
            className={menuItemClass}
            onClick={() => onOpenChange(false)}
          >
            Manage tools
          </Link>

          {hasBilling ? (
            <>
              <div role="separator" className="my-1 border-t border-border" />
              <p role="presentation" className="px-3 py-1.5 text-label-md text-muted-foreground">
                Billing
              </p>
              {canDeactivate ? (
                <button
                  type="button"
                  role="menuitem"
                  className={menuItemClass}
                  onClick={() => run(onDeactivatePlan)}
                >
                  Deactivate plan
                </button>
              ) : null}
              {canWaive ? (
                <button
                  type="button"
                  role="menuitem"
                  className={menuItemClass}
                  onClick={() => run(onWaivePayment)}
                >
                  Waive payment
                </button>
              ) : null}
            </>
          ) : null}

          <div role="separator" className="my-1 border-t border-border" />
          <p role="presentation" className="px-3 py-1.5 text-label-md text-muted-foreground">
            Access
          </p>
          <button
            type="button"
            role="menuitem"
            className={cn(menuItemClass, !tenantActive && "text-primary")}
            onClick={() => run(onToggleSuspend)}
          >
            {tenantActive ? "Suspend tenant" : "Unsuspend tenant"}
          </button>
        </div>
      ) : null}
    </div>
  );
}
