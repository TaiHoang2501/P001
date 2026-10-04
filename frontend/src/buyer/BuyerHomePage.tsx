import { Link } from "react-router";

import { useAuth } from "../auth/AuthContext";
import { ArrowRightIcon, CheckIcon } from "./icons";

const BENEFITS = ["Tìm đúng căn", "Kết nối trực tiếp chủ căn", "Đặt lịch xem nhanh chóng", "Hạn chế chia sẻ thông tin cá nhân"];

/** Wireframe 1.1: buyer landing. */
export function BuyerHomePage() {
  const { user } = useAuth();
  const start = user?.role === "CUSTOMER" ? "/buyer/chat" : "/buyer/start";

  return (
    <section className="grid items-center gap-10 overflow-hidden rounded-3xl bg-white p-6 shadow-sm ring-1 ring-line md:grid-cols-[1.1fr_1fr] md:p-12">
      <div>
        <h1 className="text-4xl font-bold leading-tight tracking-tight md:text-5xl">
          Tìm ngôi nhà Vinhomes phù hợp cùng <span className="text-brand-600">Trợ lý AI</span>
        </h1>
        <ul className="mt-7 space-y-3">
          {BENEFITS.map((b) => (
            <li key={b} className="flex items-center gap-3 text-muted">
              <span className="grid size-6 place-items-center rounded-full bg-emerald-50 text-emerald-600">
                <CheckIcon className="size-4" />
              </span>
              {b}
            </li>
          ))}
        </ul>
        <Link to={start} className="btn-primary mt-9 rounded-xl px-7 py-3.5 text-base">
          Bắt đầu với AI
          <ArrowRightIcon className="size-5" />
        </Link>
        {user?.role !== "CUSTOMER" && (
          <p className="mt-3 text-xs text-muted">Người mới có thể trò chuyện ngay, chỉ cần đăng ký khi gửi yêu cầu xem nhà.</p>
        )}
      </div>

      <Skyline />
    </section>
  );
}

/** Decorative tower illustration standing in for the hero photo. */
function Skyline() {
  return (
    <div aria-hidden="true" className="relative h-72 overflow-hidden rounded-2xl bg-gradient-to-b from-sky-200 via-sky-100 to-white md:h-96">
      <svg viewBox="0 0 400 360" preserveAspectRatio="xMidYMax slice" className="absolute inset-0 size-full">
        <defs>
          <linearGradient id="tower" x1="0" x2="1">
            <stop offset="0" stopColor="#dbe7ff" />
            <stop offset="1" stopColor="#9fb8e8" />
          </linearGradient>
          <linearGradient id="tower-front" x1="0" x2="1">
            <stop offset="0" stopColor="#eef4ff" />
            <stop offset="1" stopColor="#7d9bd6" />
          </linearGradient>
        </defs>
        <rect x="40" y="120" width="60" height="240" fill="url(#tower)" opacity="0.7" />
        <rect x="300" y="100" width="70" height="260" fill="url(#tower)" opacity="0.7" />
        <rect x="120" y="40" width="80" height="320" rx="3" fill="url(#tower-front)" />
        <rect x="215" y="10" width="75" height="350" rx="3" fill="url(#tower-front)" />
        {Array.from({ length: 16 }, (_, i) => (
          <g key={i} stroke="#ffffff" strokeOpacity="0.8">
            <line x1="126" x2="194" y1={60 + i * 18} y2={60 + i * 18} />
            <line x1="221" x2="284" y1={30 + i * 20} y2={30 + i * 20} />
          </g>
        ))}
        <rect x="0" y="330" width="400" height="30" fill="#c9e3d2" />
        <rect x="0" y="345" width="400" height="15" fill="#9fd0b4" />
      </svg>
    </div>
  );
}
