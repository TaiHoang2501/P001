import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { api, call, setAuthToken, setUnauthorizedHandler } from "../api/client";
import type { components } from "../api/schema";
import type { TokenResponse, User } from "../api/types";

type RegisterInput = components["schemas"]["RegisterRequest"];
type OtpVerifyInput = components["schemas"]["OtpVerifyRequest"];
type OtpRequestResult = components["schemas"]["OtpRequestResponse"];
type OtpRequestOptions = { role?: "CUSTOMER" | "OWNER"; purpose?: "login" | "signup" };

interface AuthState {
  user: User | null;
  login: (identifier: string, password: string) => Promise<User>;
  /** Login sends a code to any account; `purpose: "signup"` refuses a phone that already has one (PHONE_IN_USE) */
  requestOtp: (target: string, opts?: OtpRequestOptions) => Promise<OtpRequestResult>;
  verifyOtp: (input: OtpVerifyInput) => Promise<User>;
  register: (input: RegisterInput) => Promise<User>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);
const STORAGE_KEY = "bookingbot.session";

function loadSession(): TokenResponse | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as TokenResponse) : null;
  } catch {
    return null;
  }
}

function saveSession(session: TokenResponse | null) {
  try {
    if (session) localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Storage blocked (private mode): session lasts until reload
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [session, setSession] = useState<TokenResponse | null>(() => {
    const s = loadSession();
    setAuthToken(s?.access_token ?? null);
    return s;
  });

  const apply = useCallback(
    (next: TokenResponse | null) => {
      setAuthToken(next?.access_token ?? null);
      saveSession(next);
      setSession(next);
      queryClient.clear(); // never show one user's cached data to another
    },
    [queryClient],
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

  const register = useCallback(
    async (input: RegisterInput) => {
      const res = await call(api.POST("/api/v1/auth/register", { body: input }));
      apply(res);
      return res.user;
    },
    [apply],
  );

  const value = useMemo(
    () => ({ user: session?.user ?? null, login, requestOtp, verifyOtp, register, logout }),
    [session, login, requestOtp, verifyOtp, register, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
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
