import { Children, isValidElement, useEffect, useRef, useState } from "react";
import type { ComponentProps, ReactNode } from "react";
import { Plus, X, Trash2, Download, Pause, Play, FolderOpen, Copy, RotateCcw,
  Check, ArrowLeft, ArrowRight, ArrowUp, ArrowDown, ArrowUpToLine, Maximize, Settings, GripVertical,
  MoreHorizontal, Columns2, ZoomIn, ZoomOut, MousePointer2, Info, History,
  Clock, CalendarDays, Video, FileText, Gauge, WandSparkles, ScanFace, Power,
  Square, LayoutGrid, PanelBottomClose, ShieldCheck, ListChecks, Pencil } from "lucide-react";
import type { LucideIcon } from "lucide-react";

function text(node: ReactNode): string {
  return Children.toArray(node).map(child => typeof child === "string" || typeof child === "number"
    ? String(child) : isValidElement<{ children?: ReactNode }>(child) ? text(child.props.children) : "").join(" ");
}
function existingIcon(node: ReactNode): boolean {
  return Children.toArray(node).some(child => isValidElement<{ children?: ReactNode; name?: string }>(child) &&
    (child.type === "svg" || (child.props.name !== undefined && ["Home", "History", "Schedule", "Models", "Settings"].includes(child.props.name)) || existingIcon(child.props.children)));
}
export function ActionButton({ children, icon, ...props }: ComponentProps<"button"> & { icon?: LucideIcon }) {
  const [feedback, setFeedback] = useState("");
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  useEffect(() => () => clearTimeout(timer.current), []);
  const label = text(children).trim() || String(props["aria-label"] || props.title || "");
  const name = (props["aria-label"] || label).toLowerCase();
  const copying = /^copy(?:\s|$)/.test(name);
  const Glyph = icon || (label === "⋯" ? MoreHorizontal : label === "⋮⋮" ? GripVertical : label === "↔" ? Columns2 : name.includes("delete") || name.includes("remove") || name.includes("uninstall") || name.includes("recycle") || name.includes("clear history") ? Trash2
    : name.includes("add") || name.startsWith("+") ? Plus
    : name.includes("install") || name.includes("download") ? Download
    : copying ? Copy : name.includes("folder") || name === "browse…" || name === "choose…" ? FolderOpen
    : name.includes("history") ? History : name.includes("tour") ? Info
    : name.includes("compare") || name.includes("try models") ? Columns2
    : name.includes("verify") ? ShieldCheck
    : name.includes("retry") || name.includes("undo") || name.includes("reset") || name.includes("restart") || name.includes("reload") ? RotateCcw
    : name.includes("pause") ? Pause : name.includes("play") || name.includes("resume") || name.startsWith("run now") ? Play
    : name.includes("close") || name.includes("cancel") || name.includes("skip") || name.includes("keep working") || name.includes("keep files") || name.includes("keep model") || name.includes("dismiss") ? X
    : name.includes("hide") ? PanelBottomClose : name.includes("full window") ? Maximize : name.includes("zoom in") ? ZoomIn : name.includes("zoom out") ? ZoomOut
    : name.includes("move to top") ? ArrowUpToLine
    : name.includes("move up") ? ArrowUp : name.includes("move down") ? ArrowDown
    : name.includes("previous frame") || name === "back" ? ArrowLeft
    : name.includes("next frame") || name === "next" ? ArrowRight
    : name.includes("all panes") ? LayoutGrid : name.includes("select all") ? ListChecks : name.includes("select") ? MousePointer2
    : name.includes("default") || name.includes("save") || name === "done" || name === "got it" || name.startsWith("use ") || name.includes("chosen") || name.includes("mark") ? Check
    : name.includes("calibrat") || name.startsWith("fast") ? Gauge
    : name.includes("settings") || name.includes("change mode") ? Settings
    : name.includes("edit") ? Pencil : name.includes("exception") ? CalendarDays
    : name.includes("hours") || name.includes("night") || name.includes("work 09") || name === "all day" ? Clock
    : name.includes("log") ? FileText : name.includes("preview") || name === "open" ? Video
    : name.includes("standard") || name.includes("cleanup") ? WandSparkles
    : name.includes("motion") ? Play : name.includes("bigger picture") ? Maximize
    : name.includes("faces") ? ScanFace : name === "turn on" ? Power : name === "stop" ? Square : Info);
  const glyphOnly = ["⋯", "⋮⋮", "↔", "×", "+"].includes(label);
  const confirmCopy = async (operation: () => unknown) => {
    clearTimeout(timer.current);
    setFeedback("");
    try {
      await operation();
      setFeedback("Copied");
      timer.current = setTimeout(() => setFeedback(""), 1700);
    } catch (error) {
      setFeedback(`Couldn't copy: ${error instanceof Error ? error.message : String(error)}`);
    }
  };
  const button = <button {...props} onClick={copying ? event => { void confirmCopy(() => props.onClick?.(event)); } : props.onClick} title={props.title || (glyphOnly ? props["aria-label"] : undefined)}>
    {!existingIcon(children) && <Glyph className="action-icon" aria-hidden="true" size={16} strokeWidth={1.8} />}
    {!glyphOnly && children}
  </button>;
  const failed = feedback.startsWith("Couldn't copy:");
  return copying ? <span className="copy-control">{button}{feedback && <span className={`copy-feedback ${failed ? "copy-failure" : ""}`} role={failed ? "alert" : "status"} onAnimationEnd={() => { if (failed) setFeedback(""); }}>{feedback}{failed && <button aria-label="Copy message" onClick={() => { void confirmCopy(() => window.desktop.copy(feedback)); }}><Copy size={16} aria-hidden="true" /></button>}</span>}</span> : button;
}
