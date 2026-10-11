/** Tile colours: the buyer area's blue-violet, or the seller area's own terracotta (its colour from the start). */
const TILE = {
  buyer: { from: "#2f7bff", to: "#6b3df5", dots: "#3b5bff" },
  seller: { from: "#d17f47", to: "#a85a28", dots: "#c67139" },
} as const;
export type BrandTone = keyof typeof TILE;

/** BookingBot logo: a home with a chat bubble (the assistant), on a coloured tile. */
export function BrandMark({ className = "size-10", tone = "buyer" }: { className?: string; tone?: BrandTone }) {
  const t = TILE[tone];
  return (
    <svg viewBox="0 0 56 56" className={`shrink-0 drop-shadow-lg ${className}`} aria-hidden="true">
      <defs>
        <linearGradient id={`bm-tile-${tone}`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor={t.from} />
          <stop offset="1" stopColor={t.to} />
        </linearGradient>
      </defs>
      <rect width="56" height="56" rx="17" fill={`url(#bm-tile-${tone})`} />
      <path d="M9 2h22a18 18 0 0 0-18 18v-9a9 9 0 0 1 9-9Z" fill="#fff" opacity="0.14" />
      {/* Home */}
      <path
        d="M14 27.5 28 16l14 11.5V40a2.5 2.5 0 0 1-2.5 2.5h-23A2.5 2.5 0 0 1 14 40Z"
        fill="none"
        stroke="#fff"
        strokeWidth="3.2"
        strokeLinejoin="round"
      />
      {/* Chat bubble with three dots inside the home */}
      <path d="M21 29.5a3 3 0 0 1 3-3h8a3 3 0 0 1 3 3v4a3 3 0 0 1-3 3h-5.5L23 39v-2.6a3 3 0 0 1-2-2.9Z" fill="#fff" />
      <circle cx="24.8" cy="31.6" r="1.2" fill={t.dots} />
      <circle cx="28" cy="31.6" r="1.2" fill={t.dots} />
      <circle cx="31.2" cy="31.6" r="1.2" fill={t.dots} />
    </svg>
  );
}

export const BRAND_GRADIENT_TEXT = "bg-gradient-to-r from-[#1463ff] to-[#6b3df5] bg-clip-text text-transparent";

/** Logo + "BookingBot" + a tagline ("Trợ lý AI Vinhomes"; the seller area says "Dành cho chủ căn").
 * `large` on the start page, compact in page headers. Same mark and colours in every area. */
export function BrandLogo({
  large = false,
  compact = false,
  tagline = "Trợ lý AI Vinhomes",
  tone = "buyer",
}: {
  large?: boolean;
  compact?: boolean;
  tagline?: string;
  tone?: BrandTone;
}) {
  return (
    <span className={`flex items-center ${large ? "gap-3.5" : "gap-2.5"}`}>
      <BrandMark className={large ? "size-14" : "size-10"} tone={tone} />
      <span className={`leading-none ${compact ? "hidden sm:block" : ""}`}>
        <span className={`block font-display font-bold tracking-tight ${large ? "text-[1.9rem]" : "text-[1.35rem]"}`}>
          Booking<span className={tone === "seller" ? "text-brand-600" : BRAND_GRADIENT_TEXT}>Bot</span>
        </span>
        <span
          className={`block font-bold uppercase text-muted ${
            large ? "mt-1 text-[0.7rem] tracking-[0.22em]" : "mt-0.5 hidden text-[0.6rem] tracking-[0.2em] sm:block"
          }`}
        >
          {tagline}
        </span>
      </span>
    </span>
  );
}
