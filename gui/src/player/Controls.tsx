import { useCallback, useEffect, useRef, useState } from "react";
import { onPlayerEvent, send } from "./ipc";
import { clamp, previewLeft, timecode, zoomAt } from "./math";
import type { Transform } from "./math";

const rates = [0.25, 0.5, 0.75, 1, 1.25, 1.5, 2, 3, 4];
export function Controls() {
  const [paused, setPaused] = useState(false), [visible, setVisible] = useState(true);
  const [position, setPosition] = useState(0), [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(100), [muted, setMuted] = useState(false), [speed, setSpeed] = useState(1);
  const [before, setBefore] = useState(false), [divider, setDivider] = useState(0.5);
  const [original, setOriginal] = useState(false), [title, setTitle] = useState("VideoEnhancer");
  const [details, setDetails] = useState(false), [help, setHelp] = useState(false), [fullscreen, setFullscreen] = useState(false);
  const [decoder, setDecoder] = useState(""), [error, setError] = useState("");
  const [speedMenu, setSpeedMenu] = useState(false);
  const speedButton = useRef<HTMLButtonElement>(null);
  const [transform, setTransform] = useState<Transform>({ scale: 1, x: 0, y: 0 });
  const [preview, setPreview] = useState<{ seconds: number; left: number; image?: string }>();
  const generation = useRef(0), activeHover = useRef(false), activity = useRef(Date.now()), bar = useRef<HTMLInputElement>(null);
  const surface = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!help) return;
    const previous = document.activeElement;
    surface.current?.querySelector<HTMLButtonElement>(".shortcuts button")?.focus();
    return () => { if (previous instanceof HTMLElement) previous.focus(); };
  }, [help]);
  const command = useCallback((type: string, args = {}) => { void send({ type, ...args }).catch((e: Error) => setError(e.message)); }, []);
  const poke = useCallback(() => { activity.current = Date.now(); setVisible(true); }, []);
  useEffect(() => {
    const stop = onPlayerEvent(event => {
      if (event.event === "loaded") {
        setTitle(String(event.title || "VideoEnhancer")); setOriginal(event.original === true);
      }
      if (event.event === "state") {
        if (typeof event.position === "number") setPosition(event.position);
        if (typeof event.duration === "number") setDuration(event.duration);
        if (typeof event.paused === "boolean") setPaused(event.paused);
        if (typeof event.decoder === "string") setDecoder(event.decoder);
      }
      if (event.event === "error") setError("This video can't be played here. Open it in your default player instead.");
      if (event.event === "previewReady" && activeHover.current && event.generation === generation.current)
        setPreview(value => value && { ...value, image: String(event.image) });
    });
    // The host sends configuration in response to this allowlisted open, after
    // both the page listener and native composition controller are ready.
    command("open", { handle: "output" });
    return stop;
  }, [command]);
  useEffect(() => {
    const timer = setInterval(() => setVisible(paused || help || details || speedMenu || Date.now() - activity.current < 2000 || !!document.querySelector(":focus-visible")), 100);
    return () => clearInterval(timer);
  }, [paused, help, details, speedMenu]);
  useEffect(() => {
    if (speedMenu) surface.current?.querySelector<HTMLButtonElement>('.speed-menu [aria-checked="true"]')?.focus();
  }, [speedMenu]);
  const seek = useCallback((seconds: number) => command("seek", { seconds: clamp(seconds, 0, duration) }), [command, duration]);
  const togglePause = useCallback(() => { command("pause", { paused: !paused }); }, [command, paused]);
  const toggleFullscreen = useCallback(() => { setFullscreen(!fullscreen); command("fullscreen", { enabled: !fullscreen }); }, [command, fullscreen]);
  const split = useCallback((fraction: number) => { setDivider(clamp(fraction, 0, 1)); command("divider", { fraction: clamp(fraction, 0, 1) }); }, [command]);
  const changeTransform = useCallback((value: Transform) => { setTransform(value); command("transform", value); }, [command]);
  const toggleBefore = useCallback(() => { if (original) { setBefore(!before); command("beforeAfter", { enabled: !before }); } }, [before, original, command]);
  const changeVolume = useCallback((percent: number) => { setVolume(clamp(percent, 0, 100)); command("volume", { percent: clamp(percent, 0, 100) }); }, [command]);
  const changeSpeed = useCallback((rate: number) => { setSpeed(rate); command("speed", { rate }); }, [command]);
  const toggleMute = useCallback(() => { setMuted(!muted); command("mute", { muted: !muted }); }, [command, muted]);
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey || (e.key !== "Escape" && e.target instanceof Element && (e.target.matches("select,input") || (e.key === " " && e.target.matches("button"))))) return;
      poke();
      switch (e.key) {
        case " ": e.preventDefault(); togglePause(); break;
        case "ArrowLeft": case "ArrowRight": e.preventDefault(); seek(position + (e.key === "ArrowRight" ? 1 : -1) * (e.shiftKey ? 1 : 5)); break;
        case "ArrowUp": case "ArrowDown": e.preventDefault(); changeVolume(volume + (e.key === "ArrowUp" ? 5 : -5)); break;
        case ",": case ".": if (paused) command("step", { forward: e.key === "." }); break;
        case "Home": seek(0); break; case "End": seek(duration); break;
        case "m": case "M": toggleMute(); break;
        case "f": case "F": toggleFullscreen(); break;
        case "d": case "D": setDetails(v => !v); break;
        case "b": case "B": toggleBefore(); break;
        case "[": case "]": changeSpeed(rates[clamp(rates.indexOf(speed) + (e.key === "]" ? 1 : -1), 0, rates.length - 1)]); break;
        case "0": changeTransform({ scale: 1, x: 0, y: 0 }); break;
        case "?": setHelp(v => !v); break;
        case "Escape": if (speedMenu) { setSpeedMenu(false); speedButton.current?.focus(); } else if (help) setHelp(false); else if (details) setDetails(false); else if (fullscreen) toggleFullscreen(); else command("close"); break;
      }
    };
    document.addEventListener("keydown", key);
    return () => document.removeEventListener("keydown", key);
  }, [command, poke, position, paused, volume, speed, duration, help, details, fullscreen, speedMenu, seek, togglePause, toggleFullscreen, toggleBefore, changeSpeed, changeVolume, changeTransform, toggleMute]);
  const hover = (event: React.PointerEvent<HTMLInputElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const fraction = clamp((event.clientX - rect.left) / rect.width, 0, 1);
    const seconds = fraction * duration;
    activeHover.current = true;
    setPreview({ seconds, left: previewLeft(fraction, rect.width) });
    command("preview", { seconds, generation: ++generation.current });
  };
  useEffect(() => {
    const element = surface.current;
    if (!element) return;
    const wheel = (event: WheelEvent) => {
      event.preventDefault(); poke();
      if (event.ctrlKey) changeTransform(zoomAt(transform, Math.exp(-event.deltaY * 0.002), event.clientX / innerWidth - 0.5, event.clientY / innerHeight - 0.5));
      else if (transform.scale > 1) { const limit = (transform.scale - 1) / 2; changeTransform({ ...transform, x: clamp(transform.x - event.deltaX / innerWidth, -limit, limit), y: clamp(transform.y - event.deltaY / innerHeight, -limit, limit) }); }
      else if (before) split(divider - event.deltaX / innerWidth);
    };
    element.addEventListener("wheel", wheel, { passive: false });
    return () => element.removeEventListener("wheel", wheel);
  }, [before, changeTransform, divider, poke, split, transform]);
  return <main ref={surface} aria-label="Video player" className={visible ? "player" : "player hidden-controls"} onPointerMove={poke} onDoubleClick={e => { if (e.target === e.currentTarget) toggleFullscreen(); }}>
    <header className="floating"><span>{title}</span><button aria-label="Close player" onClick={() => command("close")}>×</button></header>
    {error && <p role="alert" className="error">{error}</p>}
    <div className="controls floating">
      <div className="seek-wrap">{preview && <div className="preview" style={{ left: preview.left }}><img alt="Seek preview" src={preview.image} /><span>{timecode(preview.seconds)}</span></div>}
        <input ref={bar} aria-label="Seek" type="range" min="0" max={duration || 1} step="0.001" value={position} onChange={e => seek(Number(e.target.value))} onPointerMove={hover} onPointerLeave={() => { activeHover.current = false; ++generation.current; setPreview(undefined); }} />
      </div>
      <div className="control-row"><button aria-label={paused ? "Play" : "Pause"} onClick={togglePause}>{paused ? "▶" : "Ⅱ"}</button>
        <button aria-label="Previous frame" disabled={!paused} onClick={() => command("step", { forward: false })}>|◀</button><button aria-label="Next frame" disabled={!paused} onClick={() => command("step", { forward: true })}>▶|</button>
        <span className="time">{timecode(position)} / {timecode(duration)}</span>
        <button aria-label="Before / After" aria-pressed={before} disabled={!original} title={original ? "Before / After (B)" : "Before / After needs the original video."} onClick={toggleBefore}>Before / After</button>
        {before && <input aria-label="Before / After divider" type="range" min="0" max="1" step="0.001" value={divider} onChange={e => split(Number(e.target.value))} />}
        <span className="spacer" /><button aria-label="Mute" aria-pressed={muted} onClick={toggleMute}>{muted ? "Muted" : "Sound"}</button>
        <input className="volume" aria-label="Volume" type="range" min="0" max="100" value={volume} onChange={e => changeVolume(Number(e.target.value))} />
        <button ref={speedButton} aria-label="Playback speed" aria-haspopup="menu" aria-expanded={speedMenu} onClick={() => setSpeedMenu(!speedMenu)}>{speed}×</button>
        {speedMenu && <div className="speed-menu" role="menu" aria-label="Playback speed" onKeyDown={event => {
          if (!["ArrowUp", "ArrowDown", "Home", "End"].includes(event.key)) return;
          event.preventDefault(); event.stopPropagation();
          const items = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>("button"));
          const index = items.indexOf(document.activeElement as HTMLButtonElement);
          const next = event.key === "Home" ? 0 : event.key === "End" ? items.length - 1 : (index + (event.key === "ArrowDown" ? 1 : items.length - 1)) % items.length;
          items[next]?.focus();
        }}>{rates.map(rate => <button key={rate} role="menuitemradio" aria-label={`${rate}×`} aria-checked={rate === speed} onClick={() => { changeSpeed(rate); setSpeedMenu(false); speedButton.current?.focus(); }}>{rate}×</button>)}</div>}
        <button aria-label="Details" aria-expanded={details} onClick={() => setDetails(!details)}>Details</button><button aria-label="Keyboard shortcuts" aria-expanded={help} onClick={() => setHelp(!help)}>?</button><button aria-label="Fullscreen" onClick={toggleFullscreen}>⛶</button>
      </div>
    </div>
    {details && <aside aria-label="Video details"><h2>Details</h2><button aria-label="Close details" onClick={() => setDetails(false)}>×</button><dl><dt>Video</dt><dd>{title}</dd><dt>Length</dt><dd>{timecode(duration)}</dd><dt>Decoder</dt><dd>{decoder || "Loading"}</dd><dt>Zoom</dt><dd>{Math.round(transform.scale * 100)} %</dd></dl></aside>}
    {help && <section className="shortcuts" role="dialog" aria-label="Keyboard shortcuts and gestures"><button aria-label="Close shortcuts" onClick={() => setHelp(false)}>×</button><h2>Shortcuts and gestures</h2><dl>{[["Space", "Play or pause"], ["← / →", "Seek 5 s (Shift: 1 s)"], [", / .", "Step one frame while paused"], ["↑ / ↓", "Volume"], ["M", "Mute"], ["[ / ]", "Slower / faster"], ["B", "Before / After"], ["D", "Details"], ["F", "Fullscreen"], ["0", "Reset zoom"], ["Esc", "Exit fullscreen or close"], ["Ctrl + scroll", "Zoom around the cursor"], ["Two-finger scroll", "Pan, or move the split"]].map(([key, meaning]) => <div key={key}><dt>{key}</dt><dd>{meaning}</dd></div>)}</dl></section>}
  </main>;
}
