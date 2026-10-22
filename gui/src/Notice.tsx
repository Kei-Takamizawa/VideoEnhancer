import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { X } from "lucide-react";
import { ActionButton } from "./ActionButton";

export function CopyMessage({ text }: { text: string }) {
  return <ActionButton aria-label="Copy message" onClick={() => window.desktop.copy(text)} />;
}

export function Notice({ children, identity, dismiss, className = "error", dismissible = true, role = "alert", autoDismiss = false, copyText }: {
  children: ReactNode; identity: string; dismiss?(reason: "manual" | "timeout"): void; className?: string; dismissible?: boolean; role?: "alert" | "status"; autoDismiss?: boolean; copyText?: string;
}) {
  const [hidden, setHidden] = useState<string>();
  const [hover, setHover] = useState(false);
  const [focus, setFocus] = useState(false);
  const [fading, setFading] = useState("");
  const content = useRef<HTMLDivElement>(null);
  const callback = useRef(dismiss);
  callback.current = dismiss;
  useEffect(() => {
    if (!autoDismiss || hover || focus) return;
    const fade = setTimeout(() => setFading(identity), 8000);
    const hide = setTimeout(() => { setHidden(identity); callback.current?.("timeout"); }, 9000);
    return () => { clearTimeout(fade); clearTimeout(hide); };
  }, [autoDismiss, identity, hover, focus]);
  if (hidden === identity) return null;
  return <div role={role} onMouseEnter={() => { setHover(true); setFading(""); }} onMouseLeave={() => setHover(false)} onFocus={() => { setFocus(true); setFading(""); }} onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) setFocus(false); }} className={`copyable-notice ${className} ${dismissible ? "dismissible" : ""} ${fading === identity && !hover && !focus ? "notice-fading" : ""}`}>
    {dismissible && <button className="dismiss-notice" aria-label="Dismiss" onClick={() => { setHidden(identity); dismiss?.("manual"); }}><X size={16} aria-hidden="true" /></button>}
    <div ref={content}>{children}</div>
    <ActionButton aria-label="Copy message" onClick={() => {
      const copy = content.current?.cloneNode(true) as HTMLElement | undefined;
      copy?.querySelectorAll("button,.copy-feedback").forEach(node => node.remove());
      return window.desktop.copy(copyText || copy?.textContent?.trim() || identity);
    }} />
  </div>;
}
