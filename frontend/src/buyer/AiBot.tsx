/**
 * BookingBot, the assistant: a small glossy white robot (round head, dark visor with glowing blue eyes,
 * ear disc, little body with arms), drawn in SVG so nothing has to load.
 * `animated`: floats, blinks and glances around (chat header). `thinking`: looks left and right quickly while
 * the assistant is writing. Static by default, for the many small avatars beside messages.
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
      className={`relative grid shrink-0 place-items-center overflow-hidden rounded-full bg-gradient-to-br from-[#dfe7ff] to-[#f3d9ef] ${className}`}
      aria-hidden="true"
    >
      {live && <span className="bot-halo absolute inset-0 rounded-full bg-[#b9c8ff]" />}
      <svg viewBox="0 0 48 48" className={`relative size-full ${live ? "bot-float" : ""}`} fill="none">
        <defs>
          <radialGradient id="bb-shell" cx="35%" cy="28%" r="80%">
            <stop offset="0" stopColor="#ffffff" />
            <stop offset="0.65" stopColor="#eef0f7" />
            <stop offset="1" stopColor="#c9cddd" />
          </radialGradient>
          <linearGradient id="bb-visor" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#1d2547" />
            <stop offset="1" stopColor="#070a18" />
          </linearGradient>
          <radialGradient id="bb-eye" cx="50%" cy="45%" r="60%">
            <stop offset="0" stopColor="#bfe6ff" />
            <stop offset="0.55" stopColor="#3f8cff" />
            <stop offset="1" stopColor="#2141c9" />
          </radialGradient>
        </defs>

        {/* Body with little arms */}
        <ellipse cx="11.5" cy="41" rx="3.4" ry="4.4" fill="url(#bb-shell)" transform="rotate(20 11.5 41)" />
        <ellipse cx="36.5" cy="41" rx="3.4" ry="4.4" fill="url(#bb-shell)" transform="rotate(-20 36.5 41)" />
        <path d="M14 48 C14 39 18 35.5 24 35.5 C30 35.5 34 39 34 48 Z" fill="url(#bb-shell)" />
        <rect x="21.6" y="40.5" width="4.8" height="1.3" rx="0.65" fill="#9aa1b8" />
        {/* Neck */}
        <rect x="20.5" y="33" width="7" height="3.4" rx="1.4" fill="#3b3f52" />

        {/* Ear disc */}
        <ellipse cx="8.8" cy="21" rx="3.3" ry="5" fill="#c9cddd" />
        <ellipse cx="8.4" cy="21" rx="2.1" ry="3.6" fill="#4a3448" />
        {/* Round glossy head */}
        <ellipse cx="25" cy="20" rx="15.5" ry="14" fill="url(#bb-shell)" />
        {/* Visor, with a warm rim */}
        <rect x="17" y="12.2" width="20.5" height="14.6" rx="7" fill="#f2b84b" opacity="0.55" />
        <rect x="17.4" y="12.6" width="19.7" height="13.8" rx="6.7" fill="url(#bb-visor)" />
        {/* The two eyes: blink, and glance (idle) or look around fast (thinking) */}
        <g className={thinking ? "bot-look" : live ? "bot-glance" : ""}>
          <circle cx="23.4" cy="19.6" r="2.9" fill="url(#bb-eye)" className={live ? "bot-blink" : ""} />
          <circle cx="31.4" cy="19.6" r="2.5" fill="url(#bb-eye)" className={live ? "bot-blink" : ""} />
          <circle cx="22.6" cy="18.6" r="0.75" fill="white" opacity="0.9" />
          <circle cx="30.7" cy="18.7" r="0.65" fill="white" opacity="0.9" />
        </g>
        {/* Shine on the head and visor */}
        <ellipse cx="18" cy="9.5" rx="5.5" ry="2.2" fill="white" opacity="0.8" transform="rotate(-18 18 9.5)" />
        <path d="M33.5 14 Q36 16.5 35.4 21" stroke="white" strokeWidth="0.9" strokeLinecap="round" opacity="0.45" />
      </svg>
    </span>
  );
}
