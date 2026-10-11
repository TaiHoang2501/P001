import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router";

/** How long the jumped-to item stays lit (matches the `jump-flash` animation in index.css). */
const FLASH_MS = 2600;

/**
 * Jump to an item and make it stand out, like opening a pinned message in Zalo or Messenger: when the page was
 * opened from a notification (`?jump=<time>` in the address) and `active` says this element is the item the
 * notification is about, it is scrolled to the middle of the screen and flashes for a moment.
 * Returns a ref callback for that element. Clicking the same notification again flashes it again.
 */
export function useJumpFlash(active: boolean) {
  const [params] = useSearchParams();
  const jump = params.get("jump");
  const [el, setEl] = useState<HTMLElement | null>(null);
  const ref = useCallback((node: HTMLElement | null) => setEl(node), []);

  useEffect(() => {
    if (!active || !jump || !el) return;
    // After layout settles (panels open, lists render), so it lands in the right place
    const start = window.setTimeout(() => {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      el.classList.remove("jump-flash");
      void el.offsetWidth; // restart the animation when the same notification is clicked again
      el.classList.add("jump-flash");
    }, 150);
    const end = window.setTimeout(() => el.classList.remove("jump-flash"), 150 + FLASH_MS);
    return () => {
      window.clearTimeout(start);
      window.clearTimeout(end);
    };
  }, [active, jump, el]);

  return ref;
}

/** The `jump` part of a link that opens an item from a notification (a fresh value flashes it every time). */
export function jumpParam(): string {
  return `jump=${Date.now()}`;
}
