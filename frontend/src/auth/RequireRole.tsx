import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router";

import type { Role } from "../api/types";
import { homePathFor, useAuth } from "./AuthContext";

/** Route guard: not logged in -> /login (then back here); wrong role -> that role's home. */
export function RequireRole({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { user } = useAuth();
  const location = useLocation();
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  if (!roles.includes(user.role)) return <Navigate to={homePathFor(user)} replace />;
  return <>{children}</>;
}
