import { useEffect, useRef, useState } from "react";
import { ActionButton } from "./ActionButton";

export function UndoToast({ moved, undo, expire, pause }: {
  moved: boolean; undo(): void; expire(): void; pause(paused: boolean): void;
}) {
  const [left, setLeft] = useState(10000);
  const [hover, setHover] = useState(false), [focus, setFocus] = useState(false);
  const paused = hover || focus;
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const callbacks = useRef({ expire, pause });
  const previousPause = useRef(false);
  callbacks.current = { expire, pause };
  useEffect(() => {
    if (previousPause.current !== paused) { previousPause.current = paused; callbacks.current.pause(paused); }
  }, [paused]);
  useEffect(() => {
    if (paused) return;
    let last = performance.now();
    const timer = setInterval(() => {
      const now = performance.now(), elapsed = now - last; last = now;
      setLeft(old => Math.max(0, old - elapsed));
    }, reduced ? 1000 : 50);
    return () => clearInterval(timer);
  }, [paused, reduced]);
  useEffect(() => { if (left <= 0) callbacks.current.expire(); }, [left]);
  return <div className="zoom-toast undo-toast" onPointerEnter={() => setHover(true)} onPointerLeave={() => setHover(false)}
    onFocus={() => setFocus(true)} onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) setFocus(false); }}>
    <span className="undo-tint" aria-hidden="true" style={{ width: `${left / 100}%`, transition: reduced || paused ? "none" : "width 50ms linear" }} />
    <span role="status">Removed from history{moved && <span>Files are in the Recycle Bin. Undo restores only records.</span>}</span>
    <ActionButton onClick={undo}>Undo</ActionButton>
  </div>;
}
