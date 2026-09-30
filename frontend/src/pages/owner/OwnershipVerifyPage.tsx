import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router";

import { api, ApiError, call } from "../../api/client";
import type { OwnershipChallenge, OwnershipVerification } from "../../api/types";
import { ErrorBox, Notice, PageHeader, Spinner } from "../../components/ui";
import { formatDateTime } from "../../lib/format";

/** Red books the seller has verified; each one can back one listing. */
export function useRedBooks() {
  return useQuery({ queryKey: ["owner-ownership"], queryFn: () => call(api.GET("/api/v1/owner/ownership")) });
}

/** Unused verified red books, i.e. homes the seller may list now. */
export function usableRedBooks(books: OwnershipVerification[] | undefined): OwnershipVerification[] {
  return (books ?? []).filter((b) => b.status === "VERIFIED" && b.property_id == null);
}

/**
 * Proving ownership before selling: the seller types the holder name + red book code exactly as in the
 * investor's records, then the OTP sent to the owner's phone on record.
 */
export function OwnershipVerifyPage() {
  const books = useRedBooks();

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title="Xác thực sổ đỏ"
        subtitle="Bạn chỉ đăng bán được căn có sổ đỏ đã xác thực. Mỗi sổ đỏ dùng cho một tin đăng."
      />
      <div className="grid gap-6 md:grid-cols-[1fr_1fr]">
        <VerifyForm />
        <section className="space-y-3" aria-labelledby="books-title">
          <h2 id="books-title" className="font-semibold">
            Sổ đỏ đã xác thực
          </h2>
          {books.isPending && <Spinner />}
          {books.isError && <ErrorBox error={books.error} onRetry={() => books.refetch()} />}
          {books.data?.length === 0 && <p className="text-sm text-muted">Chưa có sổ đỏ nào.</p>}
          <ul className="space-y-2">
            {books.data?.map((b) => (
              <li key={b.id} className="card p-4 text-sm">
                <p className="font-medium">{b.red_book_holder_name}</p>
                <p className="font-mono text-xs text-muted">{b.red_book_code}</p>
                {b.verified_at && <p className="mt-1 text-xs text-muted">Xác thực lúc {formatDateTime(b.verified_at)}</p>}
                <div className="mt-2">
                  {b.property_id == null ? (
                    <Link to={`/owner/properties/new?verification=${b.id}`} className="btn-primary btn-sm">
                      Đăng bán căn này
                    </Link>
                  ) : (
                    <Link to={`/owner/properties/${b.property_id}/edit`} className="text-brand-700 hover:underline">
                      Đã dùng cho tin #{b.property_id}
                    </Link>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </section>
      </div>
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
      <div className="card h-fit space-y-4 p-5">
        <Notice tone="success">
          Đã xác thực sổ đỏ <strong className="font-mono">{done.red_book_code}</strong> của {done.red_book_holder_name}. Hồ sơ của bạn
          được gửi tới Chủ đầu tư để duyệt; bạn có thể soạn tin đăng ngay trong lúc chờ.
        </Notice>
        <div className="flex flex-wrap gap-2">
          {done.property_id == null ? (
            <Link to={`/owner/properties/new?verification=${done.id}`} className="btn-primary">
              Đăng bán căn này
            </Link>
          ) : (
            <Link to={`/owner/properties/${done.property_id}/edit`} className="btn-primary">
              Xem tin đăng
            </Link>
          )}
          <button type="button" className="btn-secondary" onClick={reset}>
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
        className="card h-fit space-y-4 p-5"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          confirm.mutate();
        }}
      >
        <h2 className="font-semibold">Bước 2 · Nhập mã OTP</h2>
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
            className="input font-mono tracking-widest"
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
          <button type="submit" className="btn-primary" disabled={otp.length !== 6 || confirm.isPending || locked}>
            {confirm.isPending ? "Đang xác thực..." : "Xác thực"}
          </button>
          <button type="button" className="btn-secondary" disabled={claim.isPending || locked} onClick={() => claim.mutate()}>
            Gửi lại mã
          </button>
          <button type="button" className="btn-secondary" onClick={reset}>
            Nhập lại thông tin sổ
          </button>
        </div>
      </form>
    );
  }

  const conflict = claim.error instanceof ApiError && claim.error.code === "STATE_CONFLICT" ? claim.error.details.reason : undefined;
  return (
    <form
      className="card h-fit space-y-4 p-5"
      onSubmit={(e: FormEvent) => {
        e.preventDefault();
        claim.mutate();
      }}
    >
      <h2 className="font-semibold">Bước 1 · Thông tin trên sổ đỏ</h2>
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
          className="input"
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
          className="input font-mono uppercase"
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
