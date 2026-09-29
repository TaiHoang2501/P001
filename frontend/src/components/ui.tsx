import type { ReactNode } from "react";

import { errorMessage } from "../api/client";
import type { BookingStatus, PropertyStatus } from "../api/types";
import { BOOKING_STATUS, PROPERTY_STATUS } from "../lib/format";

export function Spinner({ label = "Đang tải..." }: { label?: string }) {
  return (
    <div role="status" className="flex items-center gap-2 py-8 text-sm text-muted">
      <span className="size-4 animate-spin rounded-full border-2 border-brand-200 border-t-brand-600" />
      {label}
    </div>
  );
}

export function ErrorBox({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-start justify-between gap-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
      <span>{errorMessage(error)}</span>
      {onRetry && (
        <button type="button" className="btn-secondary btn-sm shrink-0" onClick={onRetry}>
          Thử lại
        </button>
      )}
    </div>
  );
}

export function Notice({ tone = "info", children }: { tone?: "info" | "success" | "warning"; children: ReactNode }) {
  const styles = {
    info: "border-sky-200 bg-sky-50 text-sky-900",
    success: "border-emerald-200 bg-emerald-50 text-emerald-900",
    warning: "border-amber-200 bg-amber-50 text-amber-900",
  }[tone];
  return <div className={`rounded-lg border p-3 text-sm ${styles}`}>{children}</div>;
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="card flex flex-col items-center gap-2 px-6 py-12 text-center">
      <p className="font-medium">{title}</p>
      {children && <div className="text-sm text-muted">{children}</div>}
    </div>
  );
}

const BOOKING_TONE: Record<BookingStatus, string> = {
  REQUESTED: "bg-amber-100 text-amber-900",
  CONFIRMED: "bg-emerald-100 text-emerald-900",
  RESCHEDULE_REQUESTED: "bg-violet-100 text-violet-900",
  REJECTED: "bg-red-100 text-red-800",
  CANCELLED: "bg-stone-200 text-stone-700",
  COMPLETED: "bg-sky-100 text-sky-900",
  NO_SHOW: "bg-stone-200 text-stone-700",
};

const PROPERTY_TONE: Record<PropertyStatus, string> = {
  DRAFT: "bg-stone-200 text-stone-700",
  PENDING_REVIEW: "bg-amber-100 text-amber-900",
  AVAILABLE: "bg-emerald-100 text-emerald-900",
  REJECTED: "bg-red-100 text-red-800",
  SOLD: "bg-sky-100 text-sky-900",
  WITHDRAWN: "bg-stone-200 text-stone-700",
};

function Badge({ className, children }: { className: string; children: ReactNode }) {
  return <span className={`inline-flex shrink-0 items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${className}`}>{children}</span>;
}

export function BookingBadge({ status }: { status: BookingStatus }) {
  return <Badge className={BOOKING_TONE[status]}>{BOOKING_STATUS[status]}</Badge>;
}

export function PropertyBadge({ status }: { status: PropertyStatus }) {
  return <Badge className={PROPERTY_TONE[status]}>{PROPERTY_STATUS[status]}</Badge>;
}

export function PageHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="page-title">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}
