import { useEffect, useRef, useState } from "react";
import { ActionButton } from "./ActionButton";

export function Licences({ close }: { close(): void }) {
  const [notices, setNotices] = useState<{ text: string; path: string }>();
  const [error, setError] = useState("");
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    heading.current?.focus();
    let active = true;
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") { event.preventDefault(); close(); } };
    document.addEventListener("keydown", escape);
    void (window.desktop.licences?.() ?? Promise.reject(new Error("Licence notices are unavailable.")))
      .then(value => { if (active) setNotices(value); })
      .catch(error => { if (active) setError(String(error instanceof Error ? error.message : error)); });
    return () => { active = false; document.removeEventListener("keydown", escape); };
  }, [close]);
  return <section className="licences-view" aria-labelledby="licences-heading">
    <div className="page-heading"><h1 id="licences-heading" tabIndex={-1} ref={heading}>Open-source licences</h1>
      <ActionButton onClick={close}>Close</ActionButton>
      <ActionButton disabled={!notices} onClick={() => { if (notices) void window.desktop.reveal(notices.path).catch(error => setError(String(error))); }}>Show file</ActionButton>
    </div>
    {error && <p role="alert">{error}</p>}
    {notices ? <textarea className="licence-notices" aria-label="Licence notices" readOnly value={notices.text} /> : !error && <p role="status">Loading notices…</p>}
  </section>;
}
