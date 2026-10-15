import { useState } from "react";
import type { ReactNode } from "react";
import { X } from "lucide-react";

export function Notice({ children, identity, dismiss, className = "error", dismissible = true, role = "alert" }: {
  children: ReactNode; identity: string; dismiss?(): void; className?: string; dismissible?: boolean; role?: "alert" | "status";
}) {
  const [hidden, setHidden] = useState<string>();
  if (hidden === identity) return null;
  return <div role={role} className={`${className} ${dismissible ? "dismissible" : ""}`}>
    {dismissible && <button className="dismiss-notice" aria-label="Dismiss" onClick={() => { setHidden(identity); dismiss?.(); }}><X size={16} aria-hidden="true" /></button>}
    {children}
  </div>;
}
