import { Navigate, Route, Routes } from "react-router";

import { RequireRole } from "./auth/RequireRole";
import { Layout } from "./components/Layout";
import { EmptyState } from "./components/ui";
import { ChatPage } from "./pages/ChatPage";
import { LoginPage } from "./pages/LoginPage";
import { MyBookingsPage } from "./pages/MyBookingsPage";
import { PropertyDetailPage } from "./pages/PropertyDetailPage";
import { RegisterPage } from "./pages/RegisterPage";
import { useAuth } from "./auth/AuthContext";

/** Buyers land straight in the AI assistant after login; there is no search/filter page (spec §4.4). */
function Home() {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== "CUSTOMER") return <EmptyState title="Trang dành cho chủ căn / Chủ đầu tư đang được bổ sung" />;
  return <ChatPage />;
}

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

        {/* Customer */}
        <Route
          path="bookings"
          element={
            <RequireRole roles={["CUSTOMER"]}>
              <MyBookingsPage />
            </RequireRole>
          }
        />

        <Route path="*" element={<EmptyState title="Không tìm thấy trang" />} />
      </Route>
    </Routes>
  );
}
