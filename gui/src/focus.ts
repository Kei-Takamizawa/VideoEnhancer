import { useEffect } from "react";
export function useDialogFocus() {
  useEffect(() => {
    let previous: HTMLElement | null = null;
    let current: HTMLElement | null = null;
    const editable = (dialog: HTMLElement) =>
      Array.from(
        dialog.querySelectorAll<HTMLElement>(
          'button:not(:disabled),input:not(:disabled),select:not(:disabled),a[href],[tabindex="0"]',
        ),
      ).filter((e) => e.getClientRects().length);
    const update = () => {
      const dialogs = document.querySelectorAll<HTMLElement>(
        '[aria-modal="true"]',
      );
      const next = dialogs.item(dialogs.length - 1);
      if (next === current) return;
      if (next) {
        previous = document.activeElement as HTMLElement;
        const items = editable(next);
        (items.find(item => item.matches('button') && /^(Cancel|Close|Back|Keep|Got it)/.test(item.textContent?.trim() || "")) || items[0])?.focus({ preventScroll: true });
      } else if (previous?.isConnected) previous.focus();
      current = next;
    };
    const observer = new MutationObserver(update);
    observer.observe(document.body, { childList: true, subtree: true });
    const key = (e: KeyboardEvent) => {
      if (!current) return;
      if (e.key === "Escape") {
        const safe = editable(current).find(item => item.matches('button') && /^(Cancel|Close|Back|Keep|Got it)/.test(item.textContent?.trim() || ""));
        if (safe) { e.preventDefault(); safe.click(); }
        return;
      }
      if (e.key !== "Tab") return;
      const items = editable(current);
      if (!items.length) return;
      const first = items[0],
        last = items[items.length - 1];
      if (
        e.shiftKey &&
        (document.activeElement === first ||
          !current.contains(document.activeElement))
      ) {
        e.preventDefault();
        last.focus();
      } else if (
        !e.shiftKey &&
        (document.activeElement === last ||
          !current.contains(document.activeElement))
      ) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", key);
    return () => {
      observer.disconnect();
      document.removeEventListener("keydown", key);
    };
  }, []);
}
