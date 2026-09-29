import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router";

import type { Role } from "./api/types";
import { homePathFor, useAuth } from "./auth/AuthContext";
import { RequireRole } from "./auth/RequireRole";
import { Layout } from "./components/Layout";
import { EmptyState } from "./components/ui";
import { ChatPage } from "./pages/ChatPage";
import { LoginPage } from "./pages/LoginPage";
import { MyBookingsPage } from "./pages/MyBookingsPage";
import { BookingsMonitorPage } from "./pages/operator/BookingsMonitorPage";
import { EscalationsPage } from "./pages/operator/EscalationsPage";
import { ModerationPage } from "./pages/operator/ModerationPage";
import { SellerVerificationPage } from "./pages/operator/SellerVerificationPage";
import { OwnerBookingsPage } from "./pages/owner/OwnerBookingsPage";
import { OwnerPropertiesPage } from "./pages/owner/OwnerPropertiesPage";
import { PropertyFormPage } from "./pages/owner/PropertyFormPage";
import { SlotsPage } from "./pages/owner/SlotsPage";
import { PropertyDetailPage } from "./pages/PropertyDetailPage";
import { RegisterPage } from "./pages/RegisterPage";

/** Buyers land straight in the AI assistant after login; there is no search/filter page (spec §4.4). */
function Home() {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== "CUSTOMER") return <Navigate to={homePathFor(user)} replace />;
  return <ChatPage />;
}

const as = (roles: Role[], page: ReactNode) => <RequireRole roles={roles}>{page}</RequireRole>;

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        {/* Public */}
        <Route index element={<Home />} />
        <Route path="login" element={<LoginPage />} />
        <Route path="register" element={<RegisterPage />} />
        <Route path="properties/:id" element={<PropertyDetailPage />} />
        <Route path="chat" element={<Navigate to="/" replace />} />

        {/* Buyer */}
        <Route path="bookings" element={as(["CUSTOMER"], <MyBookingsPage />)} />

        {/* Seller (spec §4.15 Seller screens) */}
        <Route path="owner" element={as(["OWNER"], <OwnerPropertiesPage />)} />
        <Route path="owner/properties/new" element={as(["OWNER"], <PropertyFormPage />)} />
        <Route path="owner/properties/:id/edit" element={as(["OWNER"], <PropertyFormPage />)} />
        <Route path="owner/properties/:id/slots" element={as(["OWNER"], <SlotsPage />)} />
        <Route path="owner/bookings" element={as(["OWNER"], <OwnerBookingsPage />)} />

        {/* Investor / Operator (spec §4.15 Operator screens) */}
        <Route path="operator" element={as(["INVESTOR_OPERATOR"], <ModerationPage />)} />
        <Route path="operator/sellers" element={as(["INVESTOR_OPERATOR"], <SellerVerificationPage />)} />
        <Route path="operator/escalations" element={as(["INVESTOR_OPERATOR"], <EscalationsPage />)} />
        <Route path="operator/bookings" element={as(["INVESTOR_OPERATOR"], <BookingsMonitorPage />)} />

        <Route path="*" element={<EmptyState title="Không tìm thấy trang" />} />
      </Route>
    </Routes>
  );
}
