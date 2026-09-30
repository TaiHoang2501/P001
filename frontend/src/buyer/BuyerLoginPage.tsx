import { Navigate, useLocation, useNavigate } from "react-router";

import { useAuth } from "../auth/AuthContext";
import { adoptGuestChat } from "./guest";
import { LoginPanel } from "../pages/LoginPage";
import { WrongAccount } from "./shared";

export function BuyerLoginPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const from = (useLocation().state as { from?: string } | null)?.from ?? "/buyer/chat";

  if (user?.role === "CUSTOMER") return <Navigate to={from} replace />;
  if (user) return <WrongAccount />;

  return (
    <div className="mx-auto max-w-sm">
      <h1 className="page-title">Đăng nhập để trò chuyện với AI</h1>
      <p className="mb-6 mt-1 text-sm text-muted">Lần đầu dùng số điện thoại, tài khoản được tạo ngay sau khi nhập mã.</p>
      <LoginPanel
        audience="buyer"
        onDone={(u) => {
          // A guest who signs in keeps the chat they started
          void adoptGuestChat(u);
          navigate(from, { replace: true });
        }}
      />
    </div>
  );
}
