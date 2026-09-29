import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router";

import { api, call } from "../../api/client";
import { EmptyState, ErrorBox, PageHeader, Spinner } from "../../components/ui";
import { formatTimeRange } from "../../lib/format";

// Viewing times are entered in Vietnam time (UTC+7, no daylight saving)
const VN_OFFSET = "+07:00";

function tomorrowVn(): string {
  const now = new Date(Date.now() + 7 * 3600_000 + 24 * 3600_000);
  return now.toISOString().slice(0, 10);
}

export function SlotsPage() {
  const propertyId = Number(useParams().id);
  const queryClient = useQueryClient();
  const [date, setDate] = useState(tomorrowVn());
  const [time, setTime] = useState("09:00");
  const [duration, setDuration] = useState(30);

  const property = useQuery({
    queryKey: ["property", propertyId],
    queryFn: () => call(api.GET("/api/v1/properties/{property_id}", { params: { path: { property_id: propertyId } } })),
  });
  const slots = useQuery({
    queryKey: ["owner-slots", propertyId],
    queryFn: () => call(api.GET("/api/v1/owner/properties/{property_id}/slots", { params: { path: { property_id: propertyId } } })),
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["owner-slots", propertyId] });

  const add = useMutation({
    mutationFn: () => {
      const start = new Date(`${date}T${time}:00${VN_OFFSET}`);
      const end = new Date(start.getTime() + duration * 60_000);
      return call(
        api.POST("/api/v1/owner/properties/{property_id}/slots", {
          params: { path: { property_id: propertyId } },
          body: { start_at: start.toISOString(), end_at: end.toISOString() },
        }),
      );
    },
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: (slotId: number) => call(api.DELETE("/api/v1/owner/slots/{slot_id}", { params: { path: { slot_id: slotId } } })),
    onSuccess: refresh,
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    add.mutate();
  }

  return (
    <div className="mx-auto max-w-3xl">
      <Link to="/owner" className="text-sm text-muted hover:text-ink">
        ← Căn của tôi
      </Link>
      <PageHeader
        title="Khung giờ tiếp khách xem nhà"
        subtitle={property.data ? `${property.data.project_name} · ${property.data.building_name} · ${property.data.unit_code}` : undefined}
      />

      <form onSubmit={onSubmit} className="card mb-6 flex flex-wrap items-end gap-3 p-4">
        <div>
          <label htmlFor="date" className="label">
            Ngày
          </label>
          <input id="date" type="date" className="input" required min={tomorrowVn()} value={date} onChange={(e) => setDate(e.target.value)} />
        </div>
        <div>
          <label htmlFor="time" className="label">
            Giờ bắt đầu
          </label>
          <input id="time" type="time" className="input" required step={900} value={time} onChange={(e) => setTime(e.target.value)} />
        </div>
        <div>
          <label htmlFor="duration" className="label">
            Thời lượng
          </label>
          <select id="duration" className="input" value={duration} onChange={(e) => setDuration(Number(e.target.value))}>
            <option value={30}>30 phút</option>
            <option value={45}>45 phút</option>
            <option value={60}>60 phút</option>
          </select>
        </div>
        <button type="submit" className="btn-primary" disabled={add.isPending}>
          + Thêm khung giờ
        </button>
        {add.isError && (
          <div className="w-full">
            <ErrorBox error={add.error} />
          </div>
        )}
      </form>

      {remove.isError && (
        <div className="mb-4">
          <ErrorBox error={remove.error} />
        </div>
      )}
      {slots.isPending && <Spinner />}
      {slots.isError && <ErrorBox error={slots.error} onRetry={() => slots.refetch()} />}
      {slots.data?.length === 0 && <EmptyState title="Chưa có khung giờ nào">Thêm khung giờ để khách có thể đặt lịch xem.</EmptyState>}
      <ul className="card divide-y divide-line">
        {slots.data?.map((s) => (
          <li key={s.id} className="flex items-center justify-between gap-3 px-4 py-3 text-sm">
            <span className="font-medium">{formatTimeRange(s.start_at, s.end_at)}</span>
            <span className="flex items-center gap-3">
              {s.is_free ? (
                <span className="text-emerald-700">Còn trống</span>
              ) : (
                <span className="text-amber-700">Đã có khách đặt</span>
              )}
              <button type="button" className="btn-danger btn-sm" disabled={!s.is_free || remove.isPending} onClick={() => remove.mutate(s.id)}>
                Xóa
              </button>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
