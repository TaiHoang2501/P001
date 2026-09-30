import { useState, type ReactNode } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router";

import type { Media, Property } from "../api/types";
import { homePathFor, useAuth } from "../auth/AuthContext";
import { bedroomsLabel, formatArea, FURNISHING, ROLE, VIEW } from "../lib/format";
import { isGuest } from "./guest";
import { BuildingIcon } from "./icons";

/** Buyer-only routes: guests go to the buyer login, other roles are asked to switch account. */
export function RequireBuyer({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const location = useLocation();
  if (!user) return <Navigate to="/buyer/login" replace state={{ from: location.pathname + location.search }} />;
  if (user.role !== "CUSTOMER") return <WrongAccount />;
  return <>{children}</>;
}

/** Chat and viewing times are open to guests (new buyers who chose to try before signing up). */
export function RequireBuyerOrGuest({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  if (user?.role === "CUSTOMER" || (!user && isGuest())) return <>{children}</>;
  if (user) return <WrongAccount />;
  return <Navigate to="/buyer/start" replace />;
}

export function WrongAccount() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  if (!user) return null;
  return (
    <div className="card mx-auto max-w-md space-y-4 p-6 text-center">
      <p className="font-semibold">Bạn đang đăng nhập bằng tài khoản {ROLE[user.role].toLowerCase()}</p>
      <p className="text-sm text-muted">Đăng xuất để tiếp tục với tư cách người xem nhà.</p>
      <div className="flex justify-center gap-2">
        <button type="button" className="btn-primary" onClick={logout}>
          Đăng xuất
        </button>
        <button type="button" className="btn-secondary" onClick={() => navigate(homePathFor(user))}>
          Về trang quản lý
        </button>
      </div>
    </div>
  );
}

/** Public images/floorplans in display order. */
export function imagesOf(p: Property): Media[] {
  return (p.media ?? []).filter((m) => m.kind === "IMAGE" || m.kind === "FLOORPLAN");
}

/** Property photo; falls back to a neutral tile when the owner has no photo or the file can't be loaded. */
export function PropertyImage({ src, alt, className = "" }: { src?: string; alt: string; className?: string }) {
  const [failed, setFailed] = useState(false);
  if (!src || failed) {
    return (
      <div className={`grid place-items-center bg-gradient-to-br from-brand-100 to-slate-200 text-brand-600/60 ${className}`}>
        <BuildingIcon className="size-8" />
      </div>
    );
  }
  return <img src={src} alt={alt} loading="lazy" onError={() => setFailed(true)} className={`object-cover ${className}`} />;
}

/** "2 PN · 72 m² · Tầng 15" */
export function specLine(p: Property): string {
  return `${bedroomsLabel(p.bedrooms)} · ${formatArea(p.area_m2)} · Tầng ${p.floor}`;
}

/** "View hồ · Full nội thất" */
export function featureLine(p: Property): string {
  return `View ${VIEW[p.view].toLowerCase()} · ${FURNISHING[p.furnishing]}`;
}

export function MatchBadge({ score }: { score: number }) {
  return (
    <span className="shrink-0 rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-700">
      Phù hợp {Math.round(score * 100)}%
    </span>
  );
}

export function BackLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link to={to} className="inline-flex items-center gap-1 text-sm text-muted hover:text-ink">
      ← {children}
    </Link>
  );
}
