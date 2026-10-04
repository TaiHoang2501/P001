import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router";

import type { Role } from "../api/types";
import { homePathFor, useAuth } from "./AuthContext";

/** Route guard: not logged in -> that area's login page (then back here); wrong role -> that role's home. */
export function RequireRole({
  roles,
  children,
}: {
  roles: Role[];
  children: ReactNode;
}) {
  const { user } = useAuth();
  const location = useLocation();
  const loginPath = roles.every((r) => r === "INVESTOR_OPERATOR")
    ? "/operator/login"
    : "/login";
  if (!user)
    return (
      <Navigate
        to={loginPath}
        replace
        state={{ from: location.pathname + location.search }}
      />
    );
  if (!roles.includes(user.role))
    return <Navigate to={homePathFor(user)} replace />;
  return <>{children}</>;
}
