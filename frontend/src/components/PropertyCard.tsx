import { Link } from "react-router";

import type { CriterionMatch, Property } from "../api/types";
import { bedroomsLabel, CRITERION, DIRECTION, formatArea, formatVnd, VIEW } from "../lib/format";

interface Props {
  property: Property;
  score?: number;
  matched?: CriterionMatch[];
  unmatched?: CriterionMatch[];
}

/** Recommendation card: facts + why it matches (spec §4.6 step 5, explainability). */
export function PropertyCard({ property: p, score, matched = [], unmatched = [] }: Props) {
  return (
    <article className="card flex flex-col overflow-hidden transition-shadow hover:shadow-md">
      <div className="flex items-start justify-between gap-3 border-b border-line bg-brand-50/60 px-4 py-3">
        <div className="min-w-0">
          <p className="truncate text-xs font-medium uppercase tracking-wide text-brand-700">{p.project_name}</p>
          <h3 className="truncate font-semibold">
            {p.building_name} · {p.unit_code}
          </h3>
        </div>
        {/* A score is only meaningful when the customer gave preferences to match against */}
        {score !== undefined && matched.length + unmatched.length > 0 && (
          <div className="shrink-0 text-right" title="Mức độ phù hợp với tiêu chí của bạn">
            <p className="text-lg font-semibold leading-none text-brand-700">{Math.round(score * 100)}%</p>
            <p className="text-[11px] text-muted">phù hợp</p>
          </div>
        )}
      </div>

      <div className="flex flex-1 flex-col gap-3 p-4">
        <p className="text-xl font-semibold">{formatVnd(p.price_vnd)}</p>
        <dl className="grid grid-cols-3 gap-x-3 gap-y-2 text-sm">
          <Fact label="Diện tích" value={formatArea(p.area_m2)} />
          <Fact label="Phòng ngủ" value={bedroomsLabel(p.bedrooms)} />
          <Fact label="Tầng" value={String(p.floor)} />
          <Fact label="Hướng" value={DIRECTION[p.direction]} />
          <Fact label="View" value={VIEW[p.view]} />
          <Fact label="Khu vực" value={p.city} />
        </dl>

        {(matched.length > 0 || unmatched.length > 0) && (
          <ul className="flex flex-wrap gap-1.5" aria-label="Mức khớp tiêu chí">
            {matched.map((m) => (
              <li key={m.criterion} className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs text-emerald-800">
                ✓ {CRITERION[m.criterion] ?? m.criterion}
              </li>
            ))}
            {unmatched.map((m) => (
              <li
                key={m.criterion}
                className="rounded-full bg-stone-100 px-2 py-0.5 text-xs text-stone-600"
                title={`Mong muốn: ${m.wanted} · Thực tế: ${m.actual}`}
              >
                ≠ {CRITERION[m.criterion] ?? m.criterion}
              </li>
            ))}
          </ul>
        )}

        <Link to={`/properties/${p.id}`} className="btn-primary mt-auto">
          Xem chi tiết & đặt lịch
        </Link>
      </div>
    </article>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="truncate font-medium">{value}</dd>
    </div>
  );
}
