/**
 * The assistant's face: a round robot head, drawn in SVG (no image to load).
 * Its face is just two eyes. `animated`: floats, blinks and glances around (chat header).
 * `thinking`: looks left and right quickly while the assistant is writing.
 * Static by default, for the many small avatars beside messages.
 * All motion stops when the visitor asks for reduced motion (see index.css).
 */
export function AiBot({
  className = "size-9",
  animated = false,
  thinking = false,
}: {
  className?: string;
  animated?: boolean;
  thinking?: boolean;
}) {
  const live = animated || thinking;
  return (
    <span
      className={`relative grid shrink-0 place-items-center rounded-full bg-brand-50 text-brand-600 ${className}`}
      aria-hidden="true"
    >
      {live && <span className="bot-halo absolute inset-0 rounded-full bg-brand-200" />}
      <svg viewBox="0 0 40 40" className={`relative size-[92%] ${live ? "bot-float" : ""}`} fill="none">
        {/* Round head */}
        <circle cx="20" cy="20" r="16" fill="currentColor" />
        {/* Face visor */}
        <ellipse cx="20" cy="21" rx="11.5" ry="8.8" fill="#0f172a" />
        {/* The two eyes: blink, and glance (idle) or look around fast (thinking) */}
        <g className={thinking ? "bot-look" : live ? "bot-glance" : ""}>
          <rect x="13.4" y="16.6" width="4.8" height="8.4" rx="2.4" fill="white" className={live ? "bot-blink" : ""} />
          <rect x="21.8" y="16.6" width="4.8" height="8.4" rx="2.4" fill="white" className={live ? "bot-blink" : ""} />
        </g>
        {/* Light on the head */}
        <ellipse cx="13.5" cy="9" rx="4" ry="1.8" fill="white" opacity="0.35" transform="rotate(-25 13.5 9)" />
      </svg>
    </span>
  );
}
