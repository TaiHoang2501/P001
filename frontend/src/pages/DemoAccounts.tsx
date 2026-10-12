import { Fragment, useState } from "react";
import { Link } from "react-router";

import { CheckIcon, ChevronRightIcon, CopyIcon } from "../buyer/icons";

/** Accounts loaded by src/db/seed.py. Buyers and sellers have no password: they sign in with phone + OTP. */
type DemoAccount = {
  role: "Người mua" | "Người bán" | "Chủ đầu tư";
  name: string;
  note: string;
  login: string;
  /** null: phone + OTP sign-in */
  password: string | null;
  where: string;
};

const SEED_PASSWORD = "Password123!";

const ACCOUNTS: DemoAccount[] = [
  { role: "Người mua", name: "Nguyễn Văn An", note: "Có sẵn nhiều lịch xem", login: "0901111222", password: null, where: "/buyer/login" },
  { role: "Người mua", name: "Trần Thị Bình", note: "Tài khoản mới", login: "0902222333", password: null, where: "/buyer/login" },
  { role: "Người bán", name: "Hoàng Thị Lan", note: "8 sổ đã xác thực, 4 căn đang bán", login: "0912345678", password: null, where: "/login" },
  { role: "Người bán", name: "Phạm Minh Tuấn", note: "Người bán đã xác thực", login: "0918765432", password: null, where: "/login" },
  { role: "Chủ đầu tư", name: "Nguyễn Quang Dũng", note: "Duyệt tin, xử lý ngoại lệ", login: "operator@vinhomes.vn", password: SEED_PASSWORD, where: "/operator/login" },
  { role: "Chủ đầu tư", name: "Trần Thu Hà", note: "Điều phối viên", login: "coordinator@vinhomes.vn", password: SEED_PASSWORD, where: "/operator/login" },
];

const ROLE_BADGE: Record<DemoAccount["role"], string> = {
  "Người mua": "bg-brand-50 text-brand-700 ring-brand-100",
  "Người bán": "bg-orange-50 text-[#9a4a22] ring-orange-100",
  "Chủ đầu tư": "bg-slate-100 text-slate-700 ring-slate-200",
};

/** Demo accounts for testers: a row shows its sign-in details when clicked. */
export function DemoAccountsTable() {
  const [open, setOpen] = useState<number | null>(null);

  return (
    <section aria-labelledby="demo-accounts-title" className="rounded-[2rem] bg-white p-5 shadow-xl shadow-slate-900/5 ring-1 ring-line sm:p-7">
      <h2 id="demo-accounts-title" className="font-display text-2xl font-bold">
        Tài khoản demo
      </h2>
      <p className="mt-1 text-sm text-muted">Bấm vào một dòng để xem tài khoản và mật khẩu.</p>

      <div className="mt-5 overflow-hidden rounded-2xl ring-1 ring-line">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs font-bold uppercase tracking-wider text-muted">
            <tr>
              <th scope="col" className="px-4 py-3">Vai trò</th>
              <th scope="col" className="px-4 py-3">Họ tên</th>
              <th scope="col" className="hidden px-4 py-3 sm:table-cell">Ghi chú</th>
              <th scope="col" className="w-10 px-4 py-3"><span className="sr-only">Mở</span></th>
            </tr>
          </thead>
          <tbody>
            {ACCOUNTS.map((a, i) => {
              const isOpen = open === i;
              return (
                <Fragment key={a.login}>
                  <tr
                    tabIndex={0}
                    aria-expanded={isOpen}
                    onClick={() => setOpen(isOpen ? null : i)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setOpen(isOpen ? null : i);
                      }
                    }}
                    className={`cursor-pointer border-t border-line outline-none transition hover:bg-brand-50/50 focus-visible:bg-brand-50 ${isOpen ? "bg-brand-50/50" : ""}`}
                  >
                    <td className="px-4 py-3">
                      <span className={`inline-block whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ${ROLE_BADGE[a.role]}`}>
                        {a.role}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-semibold">{a.name}</td>
                    <td className="hidden px-4 py-3 text-muted sm:table-cell">{a.note}</td>
                    <td className="px-4 py-3 text-muted">
                      <ChevronRightIcon className={`size-4 transition-transform ${isOpen ? "rotate-90" : ""}`} />
                    </td>
                  </tr>
                  {isOpen && (
                    <tr className="bg-brand-50/30">
                      <td colSpan={4} className="px-4 pb-4 pt-1">
                        <dl className="grid gap-2 animate-rise-in sm:grid-cols-2">
                          <Credential label={a.password ? "Email" : "Số điện thoại"} value={a.login} />
                          {a.password ? (
                            <Credential label="Mật khẩu" value={a.password} />
                          ) : (
                            <div className="rounded-xl bg-white px-3 py-2 ring-1 ring-line">
                              <dt className="text-xs text-muted">Mật khẩu</dt>
                              <dd className="text-sm">Không cần — nhập mã OTP hiện trên màn hình đăng nhập</dd>
                            </div>
                          )}
                        </dl>
                        <Link to={a.where} className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-brand-700 hover:underline">
                          Đến trang đăng nhập ({a.where})
                          <ChevronRightIcon className="size-4" />
                        </Link>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Credential({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard blocked: the value is still on screen to copy by hand
    }
  }

  return (
    <div className="flex items-center justify-between gap-2 rounded-xl bg-white px-3 py-2 ring-1 ring-line">
      <div className="min-w-0">
        <dt className="text-xs text-muted">{label}</dt>
        <dd className="truncate font-mono text-sm font-semibold">{value}</dd>
      </div>
      <button
        type="button"
        onClick={copy}
        aria-label={`Sao chép ${label.toLowerCase()}`}
        className="grid size-8 shrink-0 place-items-center rounded-lg text-muted transition hover:bg-slate-100 hover:text-ink"
      >
        {copied ? <CheckIcon className="size-4 text-emerald-600" /> : <CopyIcon className="size-4" />}
      </button>
    </div>
  );
}

const OPERATOR_STEPS = [
  <>
    Mở trang{" "}
    <Link to="/operator/login" className="font-semibold text-brand-700 hover:underline">
      /operator/login
    </Link>{" "}
    (trang riêng, không có nút dẫn từ trang người bán).
  </>,
  <>
    Nhập email <span className="font-mono font-semibold">operator@vinhomes.vn</span> và mật khẩu{" "}
    <span className="font-mono font-semibold">{SEED_PASSWORD}</span>, rồi bấm Đăng nhập.
  </>,
  <>Tab “Duyệt tin”: chấp nhận tin đăng, hoặc từ chối kèm lý do.</>,
  <>Tab “Ngoại lệ”: nhận ca, xem bối cảnh (chủ căn chưa trả lời, AI chuyển người thật, hỗ trợ xác thực sổ đỏ…) và đóng ca kèm kết quả.</>,
  <>Tab “Lịch xem”: giám sát mọi lịch xem; chỉ hủy lịch khi xử lý ngoại lệ.</>,
];

/** How to reach the investor / operator console, which is not linked from the role cards. */
export function OperatorGuide() {
  return (
    <section aria-labelledby="operator-guide-title" className="rounded-[2rem] bg-white p-5 shadow-xl shadow-slate-900/5 ring-1 ring-line sm:p-7">
      <h2 id="operator-guide-title" className="font-display text-2xl font-bold">
        Hướng dẫn vào trang Chủ đầu tư
      </h2>
      <p className="mt-1 text-sm text-muted">Dành cho quản trị viên: duyệt tin đăng, giám sát lịch xem và xử lý ngoại lệ.</p>
      <ol className="mt-5 space-y-3">
        {OPERATOR_STEPS.map((step, i) => (
          <li key={i} className="flex gap-3 text-sm leading-relaxed">
            <span className="grid size-7 shrink-0 place-items-center rounded-full bg-brand-600 text-xs font-bold text-white">{i + 1}</span>
            <span className="pt-1">{step}</span>
          </li>
        ))}
      </ol>
      <Link
        to="/operator/login"
        className="mt-6 inline-flex items-center gap-2 rounded-full bg-slate-900 px-5 py-2.5 text-sm font-bold text-white shadow-sm transition hover:bg-slate-800"
      >
        Vào trang Chủ đầu tư
        <ChevronRightIcon className="size-4" />
      </Link>
    </section>
  );
}
