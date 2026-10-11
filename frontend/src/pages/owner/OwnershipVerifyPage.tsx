import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router";

import { api, ApiError, call } from "../../api/client";
import type { OwnershipChallenge, OwnershipVerification } from "../../api/types";
import { ErrorBox, Notice } from "../../components/ui";
import { SupportForm, SupportList, type SupportPrefill } from "./OwnershipSupport";
import { RedBookList } from "./RedBooks";

/**
 * Proving ownership before selling: the seller types the holder name + red book code exactly as in the
 * investor's records, then the OTP sent to the owner's phone on record.
 */
export function OwnershipVerifyPage() {
  // A red book the automatic check cannot handle goes to the investor (support request)
  const [help, setHelp] = useState<SupportPrefill | null>(null);
  return (
    <div className="mx-auto grid max-w-6xl gap-6 lg:grid-cols-[minmax(20rem,26rem)_minmax(0,1fr)]">
      <div className="space-y-6">
        {help ? <SupportForm prefill={help} onClose={() => setHelp(null)} /> : <VerifyForm onNeedHelp={setHelp} />}
        <SupportList />
      </div>
      <section aria-labelledby="books-title">
        <h2 id="books-title" className="mb-4 font-display text-2xl font-bold">
          Sổ đỏ / sổ hồng đã xác thực
        </h2>
        <RedBookList />
      </section>
    </div>
  );
}

function VerifyForm({ onNeedHelp }: { onNeedHelp: (prefill: SupportPrefill) => void }) {
  const queryClient = useQueryClient();
  const [holder, setHolder] = useState("");
  const [code, setCode] = useState("");
  const [otp, setOtp] = useState("");
  const [challenge, setChallenge] = useState<OwnershipChallenge | null>(null);
  const [done, setDone] = useState<OwnershipVerification | null>(null);

  const claim = useMutation({
    mutationFn: () =>
      call(api.POST("/api/v1/owner/ownership/claim", { body: { red_book_holder_name: holder.trim(), red_book_code: code.trim() } })),
    onSuccess: (res) => {
      setOtp("");
      if (res.status === "VERIFIED") {
        // Already this seller's: nothing to confirm
        queryClient.invalidateQueries({ queryKey: ["owner-ownership"] });
        setDone({ id: res.verification_id, red_book_holder_name: holder.trim(), red_book_code: code.trim(), status: "VERIFIED", verified_at: null });
      } else setChallenge(res);
    },
  });

  const confirm = useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/v1/owner/ownership/{verification_id}/confirm", {
          params: { path: { verification_id: challenge!.verification_id } },
          body: { code: otp },
        }),
      ),
    onSuccess: (res) => {
      setDone(res);
      setChallenge(null);
      queryClient.invalidateQueries({ queryKey: ["owner-ownership"] });
      queryClient.invalidateQueries({ queryKey: ["owner-verification"] });
    },
  });

  function reset() {
    setHolder("");
    setCode("");
    setOtp("");
    setChallenge(null);
    setDone(null);
    claim.reset();
    confirm.reset();
  }

  if (done) {
    return (
      <div className="h-fit space-y-4 rounded-[28px] bg-sand p-6">
        <Notice tone="success">
          Đã xác thực sổ đỏ / sổ hồng <strong className="font-mono">{done.red_book_code}</strong> của {done.red_book_holder_name}. Tài khoản
          người bán của bạn đã được xác thực, bạn có thể đăng bán ngay.
        </Notice>
        <div className="flex flex-wrap gap-2">
          {done.property_id == null ? (
            <Link to={`/owner/properties/new?verification=${done.id}`} className="btn-primary rounded-full px-5">
              Đăng bán căn này
            </Link>
          ) : (
            <Link to={`/owner/properties/${done.property_id}/edit`} className="btn-primary rounded-full px-5">
              Xem tin đăng
            </Link>
          )}
          <button type="button" className="btn-secondary rounded-full px-5" onClick={reset}>
            Xác thực sổ khác
          </button>
        </div>
      </div>
    );
  }

  if (challenge) {
    const attemptsLeft = confirm.error instanceof ApiError ? (confirm.error.details.attempts_left as number | undefined) : undefined;
    const locked = confirm.error instanceof ApiError && confirm.error.details.status === "FAILED";
    return (
      <form
        className="h-fit space-y-4 rounded-[28px] bg-sand p-6"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          confirm.mutate();
        }}
      >
        <h2 className="font-display text-2xl font-bold">Nhập mã OTP</h2>
        <p className="text-sm">
          Đã gửi mã tới số điện thoại của chủ sở hữu trên sổ: <strong className="font-mono">{challenge.masked_phone}</strong>.
        </p>
        {challenge.debug_code && (
          <Notice>
            <strong>Chế độ thử nghiệm</strong> (chưa nối SMS/Zalo): mã là <strong className="font-mono">{challenge.debug_code}</strong>.
            Bản chính thức chỉ gửi mã tới điện thoại của chủ sở hữu, không hiện ở đây.
          </Notice>
        )}
        {confirm.isError && (
          <>
            <ErrorBox error={confirm.error} />
            {locked ? (
              <Notice tone="warning">
                Sổ đỏ / sổ hồng đã bị khóa do nhập sai quá nhiều lần.{" "}
                <button type="button" className="mt-2 font-semibold text-brand-700 underline" onClick={() => onNeedHelp({ reason: "LOCKED", holder, code })}>
              Gửi yêu cầu mở khóa tới Chủ đầu tư
            </button>
              </Notice>
            ) : (
              attemptsLeft !== undefined && <p className="text-xs text-muted">Còn {attemptsLeft} lần thử.</p>
            )}
          </>
        )}
        <div>
          <label htmlFor="rb-otp" className="label">
            Mã 6 số
          </label>
          <input
            id="rb-otp"
            className="input rounded-full bg-paper px-4 py-2.5 font-mono tracking-widest"
            inputMode="numeric"
            autoComplete="one-time-code"
            pattern="\d{6}"
            maxLength={6}
            required
            autoFocus
            disabled={locked}
            value={otp}
            onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))}
          />
        </div>
        <p className="text-xs text-muted">
          Không nhận được mã vì chủ sở hữu đã đổi số?{" "}
          <button type="button" className="font-semibold text-brand-700 underline" onClick={() => onNeedHelp({ reason: "NO_OTP", holder, code })}>
            Nhờ Chủ đầu tư cập nhật
          </button>
        </p>
        <div className="flex flex-wrap gap-2">
          <button type="submit" className="btn-primary rounded-full px-5" disabled={otp.length !== 6 || confirm.isPending || locked}>
            {confirm.isPending ? "Đang xác thực..." : "Xác thực"}
          </button>
          <button type="button" className="btn-secondary rounded-full px-5" disabled={claim.isPending || locked} onClick={() => claim.mutate()}>
            Gửi lại mã
          </button>
          <button type="button" className="btn-secondary rounded-full px-5" onClick={reset}>
            Nhập lại thông tin sổ
          </button>
        </div>
      </form>
    );
  }

  const conflict = claim.error instanceof ApiError ? (claim.error.details.reason as string | undefined) : undefined;
  const guessing = claim.error instanceof ApiError && claim.error.code === "RATE_LIMITED";
  return (
    <form
      className="h-fit space-y-4 rounded-[28px] bg-sand p-6"
      onSubmit={(e: FormEvent) => {
        e.preventDefault();
        claim.mutate();
      }}
    >
      <div>
        <h2 className="font-display text-2xl font-bold">Xác thực sổ đỏ / sổ hồng mới</h2>
        <p className="mt-1 text-sm text-muted">Đối chiếu với dữ liệu của Chủ đầu tư. Mỗi sổ đỏ / sổ hồng dùng cho một tin đăng.</p>
      </div>
      {claim.isError &&
        (conflict === "CLAIMED" ? (
          <Notice tone="warning">
            Sổ đỏ / sổ hồng này đã được xác thực bởi một tài khoản khác. Nếu bạn là chủ sở hữu:{" "}
            <button type="button" className="mt-2 font-semibold text-brand-700 underline" onClick={() => onNeedHelp({ reason: "CLAIMED_BY_OTHER", holder, code })}>
              gửi giấy tờ để Chủ đầu tư xử lý
            </button>
          </Notice>
        ) : conflict === "NOT_OWNER_PHONE" ? (
          <Notice tone="warning">
            Sổ này đăng ký số điện thoại của chủ sở hữu, khác số bạn đang đăng nhập. Chỉ chủ sở hữu đăng nhập bằng đúng
            số trên sổ mới tự xác thực được.
            <br />
            Là chủ sở hữu? Đăng xuất rồi đăng nhập bằng số đó. Bán thay có ủy quyền hoặc sổ đồng sở hữu?{" "}
            <button type="button" className="font-semibold text-brand-700 underline" onClick={() => onNeedHelp({ reason: "PROXY", holder, code })}>
              Gửi giấy tờ để Chủ đầu tư xác thực
            </button>
          </Notice>
        ) : conflict === "UNIT_CLAIMED" ? (
          <Notice tone="warning">
            Căn này đang có một sổ khác đã được xác thực trên hệ thống.{" "}
            <button type="button" className="font-semibold text-brand-700 underline" onClick={() => onNeedHelp({ reason: "CLAIMED_BY_OTHER", holder, code })}>
              Gửi yêu cầu để Chủ đầu tư kiểm tra
            </button>
          </Notice>
        ) : guessing ? (
          <Notice tone="warning">
            Bạn đã nhập thông tin sổ chưa khớp nhiều lần. Vui lòng thử lại sau 1 giờ, hoặc{" "}
            <button type="button" className="font-semibold text-brand-700 underline" onClick={() => onNeedHelp({ reason: "MISMATCH", holder, code })}>
              nhờ Chủ đầu tư kiểm tra
            </button>
            .
          </Notice>
        ) : conflict === "LOCKED" ? (
          <Notice tone="warning">
            Sổ đỏ / sổ hồng này đang bị khóa do nhập sai OTP quá nhiều lần.{" "}
            <button type="button" className="mt-2 font-semibold text-brand-700 underline" onClick={() => onNeedHelp({ reason: "LOCKED", holder, code })}>
              Gửi yêu cầu mở khóa
            </button>
          </Notice>
        ) : (
          <>
            <ErrorBox error={claim.error} />
            {claim.error instanceof ApiError && claim.error.code === "OWNERSHIP_NOT_MATCHED" && (
              <p className="text-xs text-muted">
                Kiểm tra lại dấu tiếng Việt của họ tên (Tuấn khác Tuan) và mã số dạng SD-XXXX-XXXXXXX như in trên sổ. Đã đúng
                mà vẫn báo sai?{" "}
                <button type="button" className="font-semibold text-brand-700 underline" onClick={() => onNeedHelp({ reason: "MISMATCH", holder, code })}>
                  Nhờ Chủ đầu tư kiểm tra
                </button>
              </p>
            )}
          </>
        ))}
      <div>
        <label htmlFor="rb-holder" className="label">
          Họ tên người đứng tên trên sổ
        </label>
        <input
          id="rb-holder"
          className="input rounded-full bg-paper px-4 py-2.5"
          required
          minLength={2}
          maxLength={255}
          autoComplete="name"
          placeholder="VD: Nguyễn Văn A"
          value={holder}
          onChange={(e) => setHolder(e.target.value)}
        />
      </div>
      <div>
        <label htmlFor="rb-code" className="label">
          Mã số sổ đỏ / sổ hồng
        </label>
        <input
          id="rb-code"
          className="input rounded-full bg-paper px-4 py-2.5 font-mono uppercase"
          required
          minLength={3}
          maxLength={100}
          placeholder="VD: SD-XXXX-XXXXXXX"
          value={code}
          onChange={(e) => setCode(e.target.value)}
        />
      </div>
      <button type="submit" className="btn-primary w-full" disabled={claim.isPending}>
        {claim.isPending ? "Đang kiểm tra..." : "Gửi mã OTP tới chủ sở hữu"}
      </button>
      <p className="text-xs text-muted">
        Họ tên (có dấu) và mã số phải khớp với dữ liệu sổ đỏ / sổ hồng của Chủ đầu tư. Chỉ chủ sở hữu, đăng nhập bằng đúng số điện thoại
        đăng ký trên sổ, mới tự xác thực được; mã OTP được gửi tới số đó.
      </p>
      <div className="rounded-2xl bg-paper/70 px-4 py-3 text-sm">
        <p className="font-semibold">Không tự xác thực được?</p>
        <p className="mt-0.5 text-xs text-muted">Bán thay có ủy quyền, sổ đồng sở hữu, thừa kế, căn chưa có sổ…</p>
        <button
          type="button"
          className="mt-2.5 inline-flex items-center gap-1.5 rounded-full border border-brand-600/40 bg-paper px-4 py-2 text-sm font-semibold text-brand-700 shadow-sm transition hover:border-brand-600 hover:bg-brand-600 hover:text-canvas active:scale-[0.98]"
          onClick={() => onNeedHelp({ reason: "PROXY", holder, code })}
        >
          Gửi yêu cầu hỗ trợ tới Chủ đầu tư
          <span aria-hidden="true">→</span>
        </button>
      </div>
    </form>
  );
}
