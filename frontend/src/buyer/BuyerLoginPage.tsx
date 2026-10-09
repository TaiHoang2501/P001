import { Navigate, useLocation, useNavigate } from "react-router";

import { sessionExpired, useAuth } from "../auth/AuthContext";
import { Notice } from "../components/ui";
import { adoptGuestChat } from "./guest";
import { AuthShell } from "../components/AuthShell";
import { LoginPanel } from "../pages/LoginPage";
import { AiBot } from "./AiBot";
import { WrongAccount } from "./shared";

export function BuyerLoginPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const from =
    (useLocation().state as { from?: string } | null)?.from ?? "/buyer/chat";

  if (user?.role === "CUSTOMER") return <Navigate to={from} replace />;
  if (user) return <WrongAccount />;

  return (
    <div className="py-4">
      <AuthShell
        tone="buyer"
        eyebrow="BookingBot · Dành cho người mua"
        headline="Tìm căn Vinhomes cùng Trợ lý AI."
        art={
          <AiBot className="size-48 shadow-2xl ring-8 ring-white/15" animated />
        }
        points={[
          {
            title: "Chỉ căn đã xác thực",
            text: "Chủ sở hữu và pháp lý từng căn đã được Vinhomes kiểm tra.",
          },
          {
            title: "Đặt lịch thẳng với chủ căn",
            text: "Trợ lý khớp lịch giúp bạn, không qua trung gian.",
          },
          {
            title: "Số điện thoại của bạn được ẩn",
            text: "Chủ căn chỉ thấy tên và khoảng ngân sách của bạn.",
          },
        ]}
        title="Đăng nhập"
        subtitle="Chỉ cần số điện thoại, không cần email hay mật khẩu."
      >
        {from.startsWith("/buyer/activity") && !sessionExpired("buyer") && (
          <div className="mb-4">
            <Notice>Đăng nhập để xem các lịch xem nhà bạn đã đặt và trạng thái của từng lịch.</Notice>
          </div>
        )}
        {sessionExpired("buyer") && (
          <div className="mb-4">
            <Notice tone="warning">
              Phiên đăng nhập đã hết hạn. Đăng nhập lại để tiếp tục; cuộc trò chuyện và câu hỏi bạn vừa gửi vẫn được giữ.
            </Notice>
          </div>
        )}
        <LoginPanel
          audience="buyer"
          onDone={(u) => {
            // A guest who signs in keeps the chat they started
            void adoptGuestChat(u);
            navigate(from, { replace: true });
          }}
        />
      </AuthShell>
    </div>
  );
}
