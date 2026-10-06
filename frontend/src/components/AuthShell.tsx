import type { ReactNode } from "react";

/**
 * Sign-in page layout: a branded panel (what you get here) beside the form. "buyer" is the blue buyer area,
 * "seller" the sand/terracotta seller area; the form itself is the same component for both.
 */
export function AuthShell({
  tone,
  eyebrow,
  headline,
  points,
  art,
  title,
  subtitle,
  children,
}: {
  tone: "buyer" | "seller";
  eyebrow: string;
  headline: string;
  points: { title: string; text: string }[];
  art: ReactNode;
  title: string;
  subtitle: string;
  children: ReactNode;
}) {
  const panel =
    tone === "buyer"
      ? "bg-gradient-to-br from-[#1463ff] via-[#2f6bff] to-[#5b3df5] text-white"
      : "bg-gradient-to-br from-[#c67139] via-[#d48a55] to-[#b5552a] text-[#fff8ef]";
  return (
    <div
      className={`${tone === "seller" ? "theme-seller" : ""} mx-auto grid w-full max-w-5xl overflow-hidden rounded-[32px] bg-white shadow-xl shadow-black/5 lg:grid-cols-[1.05fr_1fr]`}
    >
      <aside
        className={`relative hidden overflow-hidden p-10 lg:flex lg:flex-col ${panel}`}
      >
        {/* Soft shapes behind the content */}
        <span
          aria-hidden="true"
          className="absolute -right-16 -top-16 size-64 rounded-full bg-white/10"
        />
        <span
          aria-hidden="true"
          className="absolute -bottom-24 -left-10 size-72 rounded-full bg-white/10"
        />
        <p className="relative text-xs font-bold uppercase tracking-[0.2em] opacity-80">
          {eyebrow}
        </p>
        <h2 className="font-display relative mt-3 text-4xl font-bold leading-tight">
          {headline}
        </h2>
        <div className="relative my-8 flex flex-1 items-center justify-center">
          {art}
        </div>
        <ul className="relative space-y-3">
          {points.map((p) => (
            <li key={p.title} className="flex gap-3">
              <span className="mt-0.5 grid size-6 shrink-0 place-items-center rounded-full bg-white/20 text-sm font-bold">
                ✓
              </span>
              <span>
                <span className="block font-semibold">{p.title}</span>
                <span className="block text-sm opacity-85">{p.text}</span>
              </span>
            </li>
          ))}
        </ul>
      </aside>

      <section
        className={`flex flex-col justify-center p-6 sm:p-10 ${tone === "seller" ? "bg-paper" : "bg-white"}`}
      >
        <h1 className="font-display text-3xl font-bold">{title}</h1>
        <p className="mb-6 mt-1 text-muted">{subtitle}</p>
        {children}
      </section>
    </div>
  );
}

/** Seller panel art: a red book (sổ đỏ) in front of a home. */
export function RedBookHomeArt() {
  return (
    <svg
      viewBox="0 0 220 170"
      className="w-64 drop-shadow-xl"
      aria-hidden="true"
    >
      {/* Home */}
      <path d="M40 78 L110 24 L180 78 Z" fill="#fff4e6" />
      <rect x="54" y="76" width="112" height="78" rx="6" fill="#fffaf3" />
      <rect x="70" y="92" width="26" height="22" rx="3" fill="#f3c9a6" />
      <rect x="124" y="92" width="26" height="22" rx="3" fill="#f3c9a6" />
      <rect x="98" y="116" width="24" height="38" rx="3" fill="#e9a77a" />
      {/* Red book */}
      <g transform="translate(118 74) rotate(10)">
        <rect x="4" y="4" width="62" height="82" rx="6" fill="#8e241d" />
        <rect x="0" y="0" width="62" height="82" rx="6" fill="#c0392b" />
        <rect
          x="6"
          y="6"
          width="50"
          height="70"
          rx="4"
          fill="none"
          stroke="#f3c56b"
          strokeWidth="1.6"
        />
        <circle
          cx="31"
          cy="30"
          r="10"
          fill="none"
          stroke="#f3c56b"
          strokeWidth="1.8"
        />
        <path
          d="M31 23.5l1.9 4 4.4.5-3.2 3 .9 4.3-4-2.2-4 2.2.9-4.3-3.2-3 4.4-.5z"
          fill="#f3c56b"
        />
        <rect x="15" y="50" width="32" height="3.4" rx="1.7" fill="#f3c56b" />
        <rect
          x="19"
          y="58"
          width="24"
          height="2.6"
          rx="1.3"
          fill="#f3c56b"
          opacity="0.8"
        />
      </g>
      {/* Verified seal */}
      <circle cx="58" cy="140" r="17" fill="#e1eecc" />
      <path
        d="M50 140l5.5 5.5L67 134"
        stroke="#56633f"
        strokeWidth="3.4"
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
