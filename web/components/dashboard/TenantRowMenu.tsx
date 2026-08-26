"use client";

import Link from "next/link";
import { useEffect, useId, useRef } from "react";
import panel from "@/components/dashboard/panel.module.css";
import { IconMoreVertical } from "@/components/dashboard/icons";

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

  return (
    <div className={panel.rowMenu} ref={rootRef}>
      <button
        type="button"
        className={panel.rowMenuTrigger}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
        aria-label={`Actions for ${label}`}
        disabled={disabled}
        onClick={() => onOpenChange(!open)}
      >
        <IconMoreVertical size={18} />
      </button>

      {open ? (
        <div id={menuId} className={panel.rowMenuPanel} role="menu">
          <p className={panel.rowMenuLabel} role="presentation">
            Records
          </p>
          <Link
            href={`/admin/tenants/${tenantId}/billing`}
            role="menuitem"
            className={panel.rowMenuItem}
            onClick={() => onOpenChange(false)}
          >
            View billing
          </Link>

          <Link
            href={`/admin/tenants/${tenantId}/tools`}
            role="menuitem"
            className={panel.rowMenuItem}
            onClick={() => onOpenChange(false)}
          >
            Manage tools
          </Link>

          <div className={panel.rowMenuDivider} role="separator" />

          {hasBilling ? (
            <>
              <p className={panel.rowMenuLabel} role="presentation">
                Billing
              </p>
              {canDeactivate ? (
                <button
                  type="button"
                  role="menuitem"
                  className={`${panel.rowMenuItem} ${panel.rowMenuItemWarn}`}
                  onClick={() => run(onDeactivatePlan)}
                >
                  Deactivate plan
                </button>
              ) : null}
              {canWaive ? (
                <button
                  type="button"
                  role="menuitem"
                  className={panel.rowMenuItem}
                  onClick={() => run(onWaivePayment)}
                >
                  Waive payment
                </button>
              ) : null}
              <div className={panel.rowMenuDivider} role="separator" />
            </>
          ) : null}

          <p className={panel.rowMenuLabel} role="presentation">
            Access
          </p>
          <button
            type="button"
            role="menuitem"
            className={`${panel.rowMenuItem} ${tenantActive ? panel.rowMenuItemDanger : ""}`}
            onClick={() => run(onToggleSuspend)}
          >
            {tenantActive ? "Suspend tenant" : "Unsuspend tenant"}
          </button>
        </div>
      ) : null}
    </div>
  );
}
