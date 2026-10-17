import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Link } from "react-router";

import { api, call } from "../api/client";
import { BrandLogo } from "../components/Brand";
import { ArrowLeftIcon } from "../buyer/icons";

/**
 * Public privacy notice (no sign-in). Every statement here mirrors what the code does; when a setting changes
 * (src/config.py: OTP_TTL_SECONDS, JWT_EXPIRE_MINUTES, AI_TRACE_RETENTION_DAYS; src/services/rate_limit.py: 25h),
 * update this page with it.
 */
export function PrivacyPage() {
  // The support hotline is a server setting (SUPPORT_HOTLINE), served by the public assistant-status endpoint
  const status = useQuery({
    queryKey: ["assistant-status"],
    queryFn: () => call(api.GET("/api/v1/chat/assistant-status")),
    staleTime: 5 * 60_000,
    retry: false,
  });
  const hotline = status.data?.hotline;

  return (
    <div className="theme-organic min-h-dvh bg-slate-50 px-4 pb-16 text-ink">
      <header className="mx-auto flex h-20 w-full max-w-3xl items-center justify-between gap-4">
        <Link to="/" aria-label="Về trang chủ BookingBot">
          <BrandLogo />
        </Link>
        <Link to="/" className="inline-flex items-center gap-1.5 text-sm font-semibold text-muted hover:text-ink">
          <ArrowLeftIcon className="size-4" />
          Trang chủ
        </Link>
      </header>

      <main className="mx-auto w-full max-w-3xl animate-rise-in" aria-labelledby="privacy-title">
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-brand-600">Quyền riêng tư</p>
        <h1 id="privacy-title" className="mt-2 font-display text-3xl font-bold leading-tight tracking-tight sm:text-4xl">
          Chính sách quyền riêng tư
        </h1>
        <p className="mt-3 text-muted">
          BookingBot giúp người mua tìm căn Vinhomes và đặt lịch xem nhà trực tiếp với chủ căn đã xác thực. Trang này
          nói rõ chúng tôi lưu dữ liệu nào, ai được xem, lưu bao lâu và gửi cho bên nào. Đây là bản demo của dự án; dữ
          liệu của các tài khoản demo là dữ liệu giả.
        </p>

        <div className="mt-8 space-y-5">
          <Section title="1. Dữ liệu chúng tôi thu thập">
            <ul className="list-disc space-y-2 pl-5">
              <li>
                <strong>Số điện thoại và họ tên</strong> — để đăng nhập bằng mã OTP và tạo tài khoản người mua / người
                bán. Tài khoản Chủ đầu tư (Operator) dùng email và mật khẩu.
              </li>
              <li>
                <strong>Nhu cầu tìm nhà của người mua</strong> — ngân sách, số phòng ngủ, diện tích, dự án / phân khu,
                hướng, view, khung giờ muốn xem — và các lịch xem bạn đã gửi.
              </li>
              <li>
                <strong>Thông tin xác thực chủ sở hữu</strong> — họ tên chủ sở hữu và mã sổ đỏ / sổ hồng bạn nhập, để
                đối chiếu với dữ liệu của Chủ đầu tư; thông tin tin đăng (giá, mô tả, ảnh căn).
              </li>
              <li>
                <strong>Giấy tờ hỗ trợ xác thực</strong> — giấy tờ bạn tải lên khi gửi yêu cầu hỗ trợ (ủy quyền, thừa kế,
                đồng sở hữu…).
              </li>
              <li>
                <strong>Tin nhắn với Trợ lý AI</strong>. Số điện thoại, email, số CCCD và số thẻ ngân hàng bạn gõ trong
                chat được tự động che <em>trước khi</em> gửi tới mô hình AI và trước khi lưu nhật ký kỹ thuật.
              </li>
              <li>
                <strong>Địa chỉ IP</strong> của khách chưa đăng nhập khi chat, chỉ để giới hạn số tin nhắn (chống lạm
                dụng).
              </li>
              <li>Thông báo trong ứng dụng và nhật ký thao tác (audit log) của các hành động quan trọng.</li>
            </ul>
            <p className="mt-3">
              Chúng tôi <strong>không</strong> thu thập dữ liệu thanh toán: BookingBot không có thanh toán, đặt cọc hay
              ký hợp đồng. Trang web không dùng cookie quảng cáo hay công cụ phân tích của bên thứ ba.
            </p>
          </Section>

          <Section title="2. Ai được xem dữ liệu của bạn">
            <ul className="list-disc space-y-2 pl-5">
              <li>
                <strong>Chủ căn</strong> thấy họ tên và mã người mua, khoảng ngân sách, nhu cầu về căn và giờ xem bạn
                chọn. Chủ căn <strong>không</strong> thấy số điện thoại hay email của người mua.
              </li>
              <li>
                <strong>Người mua</strong> không thấy số điện thoại hay email của chủ căn. Hai bên gặp nhau theo lịch xem
                đã được chủ căn xác nhận.
              </li>
              <li>
                <strong>Mã vào cửa (QR)</strong> của buổi xem chỉ cho bảo vệ / lễ tân thấy căn, giờ hẹn, tên người xem
                và tên chủ căn — không có số điện thoại.
              </li>
              <li>
                <strong>Chủ đầu tư (Operator)</strong> thấy họ tên và số điện thoại của hai bên để xử lý ngoại lệ (chủ
                căn không phản hồi, tranh chấp sau buổi xem, hỗ trợ sổ đỏ…), và đoạn chat gần nhất với Trợ lý khi Trợ
                lý chuyển ca cho người.
              </li>
              <li>
                <strong>Giấy tờ hỗ trợ xác thực</strong> là riêng tư: chỉ người gửi và Chủ đầu tư xem được, không hiển
                thị công khai.
              </li>
              <li>
                <strong>Đội phát triển</strong> xem nhật ký kỹ thuật của từng lượt chat (tin nhắn đã che thông tin cá
                nhân, các bước Trợ lý gọi công cụ, thời gian xử lý) để sửa lỗi và giám sát chất lượng.
              </li>
              <li>Trợ lý AI không tự chia sẻ thông tin liên hệ của bạn cho người khác.</li>
            </ul>
          </Section>

          <Section title="3. Lưu trữ trong bao lâu">
            <ul className="list-disc space-y-2 pl-5">
              <li>Mã OTP: hết hạn sau 5 phút; hệ thống chỉ lưu bản băm của mã, không lưu mã gốc.</li>
              <li>Phiên đăng nhập: 24 giờ, sau đó cần đăng nhập lại.</li>
              <li>Bộ đếm tin nhắn để giới hạn tần suất (kèm IP của khách): tự xóa sau 25 giờ.</li>
              <li>
                Nhật ký kỹ thuật của các lượt chat, và cuộc trò chuyện của khách chưa đăng nhập không được gắn vào tài
                khoản nào: tự xóa sau 180 ngày.
              </li>
              <li>
                Tài khoản, tin đăng, lịch xem, thông báo và nhật ký thao tác: lưu trong thời gian tài khoản còn sử dụng
                và chưa có yêu cầu xóa.
              </li>
            </ul>
            <p className="mt-3">
              Trên trình duyệt, trang web lưu phiên đăng nhập và cuộc trò chuyện đang dở của khách trong bộ nhớ của
              trình duyệt (localStorage) trên chính thiết bị của bạn.
            </p>
          </Section>

          <Section title="4. Bên thứ ba xử lý dữ liệu">
            <ul className="list-disc space-y-2 pl-5">
              <li>
                <strong>Nhà cung cấp mô hình AI</strong> (tùy cấu hình triển khai: OpenAI, Google Gemini, Anthropic
                Claude hoặc OpenRouter) nhận tin nhắn chat <em>đã che thông tin cá nhân</em> và dữ liệu căn cần cho câu
                trả lời.
              </li>
              <li>
                <strong>Firebase Phone Auth (Google)</strong> — khi được bật, nhận số điện thoại để gửi SMS mã OTP. Số
                của tài khoản demo không bao giờ được gửi SMS.
              </li>
              <li>
                <strong>Hạ tầng lưu trữ và vận hành</strong>: máy chủ API trên Render và Google Cloud Run, trang web
                trên Vercel, cơ sở dữ liệu PostgreSQL trên Neon. Ảnh căn và giấy tờ tải lên được lưu trong cơ sở dữ liệu
                này.
              </li>
              <li>
                <strong>Công cụ giám sát AI</strong> (Langfuse, LangSmith) — chỉ khi được bật, nhận bản ghi các lượt
                chat (đã che thông tin cá nhân) để đội phát triển theo dõi chất lượng.
              </li>
            </ul>
            <p className="mt-3">Chúng tôi không bán dữ liệu cá nhân và không chia sẻ cho môi giới hay CRM bên ngoài.</p>
          </Section>

          <Section title="5. Yêu cầu xem, sửa hoặc xóa dữ liệu">
            <p>
              Bạn có thể yêu cầu xem lại, sửa hoặc xóa dữ liệu cá nhân và tài khoản của mình bằng cách liên hệ{" "}
              {hotline ? (
                <>
                  Tổng đài <strong>{hotline}</strong>
                </>
              ) : (
                "Tổng đài hỗ trợ của BookingBot"
              )}{" "}
              từ chính số điện thoại đăng ký. Chủ đầu tư sẽ xác minh bạn là chủ tài khoản rồi xử lý. Một số bản ghi (vd.
              nhật ký thao tác của lịch xem) có thể cần giữ lại để giải quyết tranh chấp.
            </p>
          </Section>
        </div>

        <p className="mt-8 text-center text-xs text-muted">Cập nhật lần cuối: tháng 10/2026.</p>
      </main>
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-3xl bg-white p-6 text-[0.95rem] leading-relaxed shadow-sm ring-1 ring-line sm:p-7">
      <h2 className="mb-3 font-display text-xl font-bold">{title}</h2>
      {children}
    </section>
  );
}

/** Small "Chính sách quyền riêng tư" link for sign-in forms and page footers. */
export function PrivacyLink({ className = "" }: { className?: string }) {
  return (
    <Link to="/privacy" className={`font-medium underline underline-offset-2 hover:text-ink ${className}`}>
      Chính sách quyền riêng tư
    </Link>
  );
}
