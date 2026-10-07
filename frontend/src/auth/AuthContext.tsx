import { QueryClientProvider, type QueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useLocation } from "react-router";

import { api, call, setAuthToken, setUnauthorizedHandler } from "../api/client";
import { newQueryClient } from "../api/queryClient";
import type { components } from "../api/schema";
import type { TokenResponse, User } from "../api/types";

type OtpVerifyInput = components["schemas"]["OtpVerifyRequest"];
type OtpRequestResult = components["schemas"]["OtpRequestResponse"];
type OtpRequestOptions = { role?: "CUSTOMER" | "OWNER"; purpose?: "login" | "signup" };

interface AuthState {
  user: User | null;
  login: (identifier: string, password: string) => Promise<User>;
  /** Login sends a code to any account; `purpose: "signup"` refuses a phone that already has one (PHONE_IN_USE) */
  requestOtp: (target: string, opts?: OtpRequestOptions) => Promise<OtpRequestResult>;
  verifyOtp: (input: OtpVerifyInput) => Promise<User>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);
/**
 * Each part of the site keeps its own sign-in, so a seller and the investor/operator (or a buyer) can be signed
 * in side by side in two tabs of one browser: signing in on one never replaces the other.
 */
export type Area = "buyer" | "seller" | "operator";

const AREA_ROLE: Record<Area, User["role"]> = { buyer: "CUSTOMER", seller: "OWNER", operator: "INVESTOR_OPERATOR" };
const ROLE_AREA: Record<User["role"], Area> = { CUSTOMER: "buyer", OWNER: "seller", INVESTOR_OPERATOR: "operator" };

/** The part of the site a page belongs to; null for shared pages (role chooser, viewing pass check). */
export function areaOf(pathname: string): Area | null {
  if (pathname.startsWith("/operator")) return "operator";
  if (pathname.startsWith("/buyer")) return "buyer";
  if (pathname.startsWith("/owner") || pathname === "/login") return "seller";
  return null;
}

const storageKey = (area: Area) => `bookingbot.session.${area}`;
// Before sign-ins were kept per area, one session was shared by the whole site
const LEGACY_KEY = "bookingbot.session";

function loadSession(area: Area | null): TokenResponse | null {
  if (!area) return null;
  try {
    const legacy = localStorage.getItem(LEGACY_KEY);
    if (legacy) {
      // Move the old shared session to the area of its role, once
      const old = JSON.parse(legacy) as TokenResponse;
      localStorage.setItem(storageKey(ROLE_AREA[old.user.role]), legacy);
      localStorage.removeItem(LEGACY_KEY);
    }
    const raw = localStorage.getItem(storageKey(area));
    const session = raw ? (JSON.parse(raw) as TokenResponse) : null;
    // Only an account of this area's kind signs this area in
    return session?.user.role === AREA_ROLE[area] ? session : null;
  } catch {
    return null;
  }
}

function saveSession(area: Area, session: TokenResponse | null) {
  try {
    if (session) localStorage.setItem(storageKey(area), JSON.stringify(session));
    else localStorage.removeItem(storageKey(area));
  } catch {
    // Storage blocked (private mode): session lasts until reload
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const area = areaOf(useLocation().pathname);
  // A data cache per area: the seller's cached data never shows on the operator's pages, or the other way round
  const caches = useRef(new Map<string, QueryClient>());
  const cacheKey = area ?? "shared";
  if (!caches.current.has(cacheKey)) caches.current.set(cacheKey, newQueryClient());
  const queryClient = caches.current.get(cacheKey)!;

  const [state, setState] = useState(() => ({ area, session: loadSession(area) }));
  let session = state.session;
  if (state.area !== area) {
    // Moved to another part of the site: use that part's own sign-in, before its pages fetch anything
    session = loadSession(area);
    setState({ area, session });
  }
  setAuthToken(session?.access_token ?? null);

  const apply = useCallback(
    (next: TokenResponse | null) => {
      setAuthToken(next?.access_token ?? null);
      // Saved for the area of the account (normally the area of the sign-in page)
      const target = next ? ROLE_AREA[next.user.role] : area;
      if (target) saveSession(target, next);
      setState({ area, session: next && (!area || target === area) ? next : null });
      queryClient.clear(); // never show one user's cached data to another
    },
    [queryClient, area],
  );

  const logout = useCallback(() => apply(null), [apply]);

  useEffect(() => {
    setUnauthorizedHandler(logout);
  }, [logout]);

  const login = useCallback(
    async (identifier: string, password: string) => {
      const res = await call(api.POST("/api/v1/auth/login", { body: { identifier, password } }));
      apply(res);
      return res.user;
    },
    [apply],
  );

  const requestOtp = useCallback(
    (target: string, opts: OtpRequestOptions = {}) =>
      call(
        api.POST("/api/v1/auth/otp/request", {
          body: { target, role: opts.role ?? null, purpose: opts.purpose ?? "login" },
        }),
      ),
    [],
  );

  const verifyOtp = useCallback(
    async (input: OtpVerifyInput) => {
      const res = await call(api.POST("/api/v1/auth/otp/verify", { body: input }));
      apply(res);
      return res.user;
    },
    [apply],
  );

  const value = useMemo(
    () => ({ user: session?.user ?? null, login, requestOtp, verifyOtp, logout }),
    [session, login, requestOtp, verifyOtp, logout],
  );
  return (
    <QueryClientProvider client={queryClient}>
      <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
    </QueryClientProvider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

export function homePathFor(user: User | null): string {
  if (user?.role === "OWNER") return "/owner";
  if (user?.role === "INVESTOR_OPERATOR") return "/operator";
  if (user?.role === "CUSTOMER") return "/buyer/chat";
  return "/";
}
