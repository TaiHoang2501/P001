import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router";

import { api, ApiError, call } from "../../api/client";
import type { OwnershipChallenge, OwnershipVerification } from "../../api/types";
import { ErrorBox, Notice } from "../../components/ui";
import { RedBookList } from "./RedBooks";

/**
 * Proving ownership before selling: the seller types the holder name + red book code exactly as in the
 * investor's records, then the OTP sent to the owner's phone on record.
 */
export function OwnershipVerifyPage() {
  return (
    <div className="mx-auto grid max-w-6xl gap-6 lg:grid-cols-[minmax(20rem,26rem)_minmax(0,1fr)]">
      <VerifyForm />
      <section aria-labelledby="books-title">
        <h2 id="books-title" className="mb-4 font-display text-2xl font-bold">
          Sổ đỏ đã xác thực
        </h2>
        <RedBookList />
      </section>
    </div>
  );
}

function VerifyForm() {
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
          Đã xác thực sổ đỏ <strong className="font-mono">{done.red_book_code}</strong> của {done.red_book_holder_name}. Hồ sơ của bạn
          được gửi tới Chủ đầu tư để duyệt; bạn có thể soạn tin đăng ngay trong lúc chờ.
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
            Môi trường thử nghiệm (chưa có nhà cung cấp SMS/Zalo): mã là <strong className="font-mono">{challenge.debug_code}</strong>
          </Notice>
        )}
        {confirm.isError && (
          <>
            <ErrorBox error={confirm.error} />
            {locked ? (
              <Notice tone="warning">Sổ đỏ đã bị khóa do nhập sai quá nhiều lần. Vui lòng liên hệ Chủ đầu tư để mở khóa.</Notice>
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

  const conflict = claim.error instanceof ApiError && claim.error.code === "STATE_CONFLICT" ? claim.error.details.reason : undefined;
  return (
    <form
      className="h-fit space-y-4 rounded-[28px] bg-sand p-6"
      onSubmit={(e: FormEvent) => {
        e.preventDefault();
        claim.mutate();
      }}
    >
      <div>
        <h2 className="font-display text-2xl font-bold">Xác thực sổ đỏ mới</h2>
        <p className="mt-1 text-sm text-muted">Đối chiếu với dữ liệu của Chủ đầu tư. Mỗi sổ đỏ dùng cho một tin đăng.</p>
      </div>
      {claim.isError &&
        (conflict === "CLAIMED" ? (
          <Notice tone="warning">Sổ đỏ này đã được xác thực bởi một tài khoản khác. Nếu bạn là chủ sở hữu, hãy liên hệ Chủ đầu tư.</Notice>
        ) : conflict === "LOCKED" ? (
          <Notice tone="warning">Sổ đỏ này đang bị khóa do nhập sai OTP quá nhiều lần. Vui lòng liên hệ Chủ đầu tư.</Notice>
        ) : (
          <ErrorBox error={claim.error} />
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
          placeholder="Nguyễn Thị Hương"
          value={holder}
          onChange={(e) => setHolder(e.target.value)}
        />
      </div>
      <div>
        <label htmlFor="rb-code" className="label">
          Mã số sổ đỏ
        </label>
        <input
          id="rb-code"
          className="input rounded-full bg-paper px-4 py-2.5 font-mono uppercase"
          required
          minLength={3}
          maxLength={100}
          placeholder="SD-2017-0332211"
          value={code}
          onChange={(e) => setCode(e.target.value)}
        />
      </div>
      <button type="submit" className="btn-primary w-full" disabled={claim.isPending}>
        {claim.isPending ? "Đang kiểm tra..." : "Gửi mã OTP tới chủ sở hữu"}
      </button>
      <p className="text-xs text-muted">
        Họ tên (có dấu) và mã số phải khớp với dữ liệu sổ đỏ của Chủ đầu tư. Mã OTP được gửi tới số điện thoại của chủ sở hữu đã đăng
        ký trên sổ.
      </p>
    </form>
  );
}
