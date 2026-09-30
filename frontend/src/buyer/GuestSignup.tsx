import { useState } from "react";

import type { User } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Notice } from "../components/ui";
import { LoginPanel } from "../pages/LoginPage";
import { adoptGuestChat } from "./guest";

/**
 * Shown to a guest at the moment they confirm a viewing: a quick phone + OTP sign-up (or sign-in if the
 * phone already has a buyer account). `onDone` runs once they are a signed-in buyer, to send the request.
 */
export function GuestSignup({ onDone }: { onDone: (user: User) => void }) {
  const { logout } = useAuth();
  const [wrongRole, setWrongRole] = useState(false);

  async function done(user: User) {
    if (user.role !== "CUSTOMER") {
      // A seller/operator phone cannot book as a buyer
      logout();
      setWrongRole(true);
      return;
    }
    await adoptGuestChat(user);
    onDone(user);
  }

  return (
    <section className="rounded-2xl border border-brand-200 bg-brand-50/60 p-4" aria-labelledby="guest-signup-title">
      <h3 id="guest-signup-title" className="font-semibold">
        Đăng ký để gửi yêu cầu xem nhà
      </h3>
      <p className="mb-3 mt-1 text-sm text-muted">
        Chỉ cần số điện thoại và mã OTP. Tài khoản giúp bạn theo dõi lịch đã đặt; chủ căn không thấy số điện thoại của bạn.
      </p>
      {wrongRole && (
        <div className="mb-3">
          <Notice tone="warning">Số điện thoại này thuộc tài khoản người bán/quản trị. Vui lòng dùng số khác.</Notice>
        </div>
      )}
      <LoginPanel audience="buyer" otpOnly onDone={(u) => void done(u)} />
    </section>
  );
}
