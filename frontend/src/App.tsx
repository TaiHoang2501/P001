import type { ReactNode } from "react";
import { Navigate, Route, Routes, useParams } from "react-router";

import type { Role } from "./api/types";
import { RequireRole } from "./auth/RequireRole";
import { BuyerChatPage } from "./buyer/BuyerChatPage";
import { ActivityPage } from "./buyer/ActivityPage";
import { BuyerHomePage } from "./buyer/BuyerHomePage";
import { BuyerLayout } from "./buyer/BuyerLayout";
import { BuyerLoginPage } from "./buyer/BuyerLoginPage";
import { BuyerStartPage } from "./buyer/BuyerStartPage";
import { RequireBuyer, RequireBuyerOrGuest } from "./buyer/shared";
import { Layout } from "./components/Layout";
import { LiveNotifications } from "./components/LiveNotifications";
import { EmptyState } from "./components/ui";
import { LoginPage, OperatorLoginPage } from "./pages/LoginPage";
import { PassCheckPage } from "./pages/PassCheckPage";
import { BookingsMonitorPage } from "./pages/operator/BookingsMonitorPage";
import { EscalationsPage } from "./pages/operator/EscalationsPage";
import { ModerationPage } from "./pages/operator/ModerationPage";
import { OwnerBookingsPage } from "./pages/owner/OwnerBookingsPage";
import { OwnershipVerifyPage } from "./pages/owner/OwnershipVerifyPage";
import { OwnerPropertiesPage } from "./pages/owner/OwnerPropertiesPage";
import { PropertyFormPage } from "./pages/owner/PropertyFormPage";
import { SlotsPage } from "./pages/owner/SlotsPage";
import { RoleSelectPage } from "./pages/RoleSelectPage";

const as = (roles: Role[], page: ReactNode) => (
  <RequireRole roles={roles}>{page}</RequireRole>
);
const buyer = (page: ReactNode) => <RequireBuyer>{page}</RequireBuyer>;
const buyerOrGuest = (page: ReactNode) => (
  <RequireBuyerOrGuest>{page}</RequireBuyerOrGuest>
);

/** /buyer/properties/:id[/schedule] opens that home as a card in the agent chat. */
function ToChat({ schedule = false }: { schedule?: boolean }) {
  const id = useParams().id;
  return (
    <Navigate
      to={`/buyer/chat?property=${id}${schedule ? "&schedule=1" : ""}`}
      replace
    />
  );
}

/** /buyer/bookings[/:id] (older links): the buyer's viewings now live on the "Hoạt động" page. */
function BookingsToActivity() {
  const id = useParams().id;
  return <Navigate to={id ? `/buyer/activity?booking=${id}` : "/buyer/activity"} replace />;
}

/** Old buyer links (/properties/:id) now live in the buyer area. */
function LegacyPropertyRedirect() {
  return <Navigate to={`/buyer/properties/${useParams().id}`} replace />;
}

export function App() {
  return (
    <>
      {/* New notifications pop up at once, for every role */}
      <LiveNotifications />
      <Routes>
      {/* Entry: "view homes" -> buyer area, "sell a home" -> BookingBot */}
      <Route index element={<RoleSelectPage />} />
      {/* Scanned at the building's gate from the buyer's QR (public) */}
      <Route path="pass/:token" element={<PassCheckPage />} />

      {/* Buyer area: AI agent chat + viewing requests (wireframe 1.1-1.6) */}
      <Route path="buyer" element={<BuyerLayout />}>
        <Route index element={<BuyerHomePage />} />
        <Route path="start" element={<BuyerStartPage />} />
        <Route path="login" element={<BuyerLoginPage />} />
        <Route path="chat" element={buyerOrGuest(<BuyerChatPage />)} />
        {/* A home's details and its viewing-time picker live inside the agent chat */}
        <Route path="properties/:id" element={<ToChat />} />
        <Route path="properties/:id/schedule" element={<ToChat schedule />} />
        <Route path="activity" element={buyer(<ActivityPage />)} />
        <Route path="bookings" element={buyer(<BookingsToActivity />)} />
        <Route path="bookings/:id" element={buyer(<BookingsToActivity />)} />
        <Route path="*" element={<EmptyState title="Không tìm thấy trang" />} />
      </Route>
      <Route path="chat" element={<Navigate to="/buyer/chat" replace />} />
      <Route
        path="bookings"
        element={<Navigate to="/buyer/bookings" replace />}
      />
      <Route path="properties/:id" element={<LegacyPropertyRedirect />} />

      {/* BookingBot: sellers and the investor/operator */}
      <Route element={<Layout />}>
        <Route path="login" element={<LoginPage />} />
        {/* Operators sign in on their own page; the seller login does not link to it */}
        <Route path="operator/login" element={<OperatorLoginPage />} />
        {/* Sellers sign up with phone + OTP on the login page; there is no password sign-up */}
        <Route path="register" element={<Navigate to="/login" replace />} />

        {/* Seller (spec §4.15 Seller screens) */}
        <Route path="owner" element={as(["OWNER"], <OwnerPropertiesPage />)} />
        <Route
          path="owner/verify"
          element={as(["OWNER"], <OwnershipVerifyPage />)}
        />
        <Route
          path="owner/properties/new"
          element={as(["OWNER"], <PropertyFormPage />)}
        />
        <Route
          path="owner/properties/:id/edit"
          element={as(["OWNER"], <PropertyFormPage />)}
        />
        <Route
          path="owner/properties/:id/slots"
          element={as(["OWNER"], <SlotsPage />)}
        />
        <Route
          path="owner/bookings"
          element={as(["OWNER"], <OwnerBookingsPage />)}
        />

        {/* Investor / Operator (spec §4.15 Operator screens) */}
        <Route
          path="operator"
          element={as(["INVESTOR_OPERATOR"], <ModerationPage />)}
        />
        <Route
          path="operator/escalations"
          element={as(["INVESTOR_OPERATOR"], <EscalationsPage />)}
        />
        <Route
          path="operator/bookings"
          element={as(["INVESTOR_OPERATOR"], <BookingsMonitorPage />)}
        />

        <Route path="*" element={<EmptyState title="Không tìm thấy trang" />} />
      </Route>
    </Routes>
    </>
  );
}
