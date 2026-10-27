import { Notice } from "./Notice";
import { ErrorBoundary } from "./ErrorBoundary";
import { ActionButton } from "./ActionButton";
import { Check, Download, Layers } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { createFile } from "mp4box";
import type { Sample } from "mp4box";
import type { Api } from "./api";
import { duration, filename } from "./api";
import type { Media, Model, Operation, Settings } from "./types";
import { OperationStatus } from "./Pages";

type Movie = { config: VideoDecoderConfig; samples: Sample[]; fps: number };
export function compareMovie<T>(cache: Map<string, Promise<T>>, path: string, load: () => Promise<T>): Promise<T> {
  const existing = cache.get(path);
  if (existing) return existing;
  const pending = load().catch(error => { cache.delete(path); throw error; });
  cache.set(path, pending);
  return pending;
}
async function demux(blob: Blob): Promise<Movie> {
  const file = createFile();
  const samples: Sample[] = [];
  let config: VideoDecoderConfig | undefined;
  let fps = 0;
  file.onError = (_module, message) => {
    throw new Error(message);
  };
  file.onReady = (info) => {
    const track = info.videoTracks[0];
    if (!track?.video) throw new Error("The preview has no video track.");
    const entry = file.getTrackById(track.id).mdia.minf.stbl.stsd.entries[0];
    if (!("avcC" in entry) || !entry.avcC)
      throw new Error("The preview must be H.264.");
    const c = entry.avcC as {
      AVCProfileIndication: number;
      profile_compatibility: number;
      AVCLevelIndication: number;
      lengthSizeMinusOne: number;
      SPS: { data: Uint8Array }[];
      PPS: { data: Uint8Array }[];
    };
    const bytes: number[] = [
      1,
      c.AVCProfileIndication,
      c.profile_compatibility,
      c.AVCLevelIndication,
      252 | c.lengthSizeMinusOne,
      224 | c.SPS.length,
    ];
    for (const set of c.SPS)
      bytes.push(set.data.length >> 8, set.data.length & 255, ...set.data);
    bytes.push(c.PPS.length);
    for (const set of c.PPS)
      bytes.push(set.data.length >> 8, set.data.length & 255, ...set.data);
    config = {
      codec: track.codec,
      codedWidth: track.video.width,
      codedHeight: track.video.height,
      description: new Uint8Array(bytes),
    };
    fps = (track.nb_samples * track.timescale) / track.samples_duration;
    file.setExtractionOptions(track.id, null, { nbSamples: 1000 });
    file.start();
  };
  file.onSamples = (_id, _user, batch) => samples.push(...batch);
  file.appendBuffer(Object.assign(await blob.arrayBuffer(), { fileStart: 0 }));
  file.flush();
  if (!config || !samples.length)
    throw new Error("The preview could not be read.");
  if (!(await VideoDecoder.isConfigSupported(config)).supported)
    throw new Error(
      "H.264 WebCodecs decoding is unavailable on this computer.",
    );
  return { config, samples, fps };
}

// Both canvases use one integer frame clock. Each decoder keeps a bounded look-ahead.
class FrameReader {
  movie: Movie;
  decoder: VideoDecoder;
  frames = new Map<number, VideoFrame>();
  cursor = 0;
  target = 0;
  flushed = false;
  error = "";
  origin: number;
  constructor(movie: Movie) {
    this.movie = movie;
    this.origin = Math.min(...movie.samples.map((s) => s.cts));
    this.decoder = new VideoDecoder({
      output: (frame) => {
        const index = Math.round((frame.timestamp / 1e6) * movie.fps);
        if (index < this.target || index > this.target + 20) frame.close();
        else {
          this.frames.get(index)?.close();
          this.frames.set(index, frame);
        }
      },
      error: (error) => {
        this.error = error.message;
      },
    });
    this.decoder.configure(movie.config);
  }
  frame(index: number) {
    if (index < this.target || index > this.target + 16) {
      this.decoder.reset();
      this.decoder.configure(this.movie.config);
      this.frames.forEach((f) => f.close());
      this.frames.clear();
      this.flushed = false;
      this.cursor = 0;
      this.movie.samples.forEach((s, n) => {
        if (
          s.is_sync &&
          Math.round(((s.cts - this.origin) / s.timescale) * this.movie.fps) <=
            index
        )
          this.cursor = n;
      });
    }
    this.target = index;
    for (const [n, f] of this.frames)
      if (n < index) {
        f.close();
        this.frames.delete(n);
      }
    while (
      this.cursor < this.movie.samples.length &&
      this.decoder.decodeQueueSize < 12
    ) {
      const sample = this.movie.samples[this.cursor];
      const n = Math.round(
        ((sample.cts - this.origin) / sample.timescale) * this.movie.fps,
      );
      if (n > index + 12) break;
      this.cursor++;
      this.decoder.decode(
        new EncodedVideoChunk({
          type: sample.is_sync ? "key" : "delta",
          timestamp: Math.round(
            ((sample.cts - this.origin) / sample.timescale) * 1e6,
          ),
          duration: Math.round((sample.duration / sample.timescale) * 1e6),
          data: sample.data!,
        }),
      );
    }
    if (this.cursor === this.movie.samples.length && !this.flushed) {
      this.flushed = true;
      void this.decoder.flush().catch((e) => {
        this.error = e.message;
      });
    }
    return this.frames.get(index);
  }
  close() {
    this.decoder.close();
    this.frames.forEach((f) => f.close());
    this.frames.clear();
  }
}

export function Compare({
  api,
  operation,
}: {
  api: Api;
  operation: Operation;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const viewport = useRef<HTMLDivElement>(null);
  const [full, setFull] = useState(false);
  const [solo, setSolo] = useState<number | null>(null);
  const pointers = useRef(new Map<number, { x: number; y: number }>());
  const gesture = useRef<{ distance: number; x: number; y: number } | null>(null);
  const readers = useRef<FrameReader[]>([]);
  const movieCache = useRef<{ operation: string; api: Api; movies: Map<string, Promise<Movie>> }>(undefined);
  const clock = useRef({ frame: 0, playing: false, anchor: 0, anchorFrame: 0 });
  const [count, setCount] = useState(0);
  const [fps, setFps] = useState(30);
  const [frame, setFrame] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [split, setSplit] = useState(50);
  const [side, setSide] = useState(true);
  const [resultOnly, setResultOnly] = useState(false);
  const [loop, setLoop] = useState(true);
  const [left, setLeft] = useState(0),
    [right, setRight] = useState(1);
  const [zoom, setZoom] = useState(100);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [error, setError] = useState("");
  const paths = operation.result?.items
    ? [
        operation.result.original!,
        ...operation.result.items.map((item) => item.preview),
      ]
    : [
        operation.result?.preview?.original,
        operation.result?.preview?.enhanced,
      ];
  const labels = operation.result?.items
    ? [
        "Original",
        ...operation.result.items.map((item) => item.name || item.id),
      ]
    : ["Original", "Enhanced"];
  const drawing = useRef({ split, side, left, right, loop, labels, resultOnly, solo });
  drawing.current = { split, side, left, right, loop, labels, resultOnly, solo };
  const interaction = useRef({ zoom, side, solo }); interaction.current = { zoom, side, solo };
  useEffect(() => {
    const element = viewport.current;
    if (!element) return;
    const wheel = (event: WheelEvent) => {
      event.preventDefault(); event.stopPropagation();
      if (event.ctrlKey) {
        const box = element.getBoundingClientRect(), x = event.clientX - box.left - box.width / 2, y = event.clientY - box.top - box.height / 2;
        const old = interaction.current.zoom, next = Math.max(100, Math.min(800, old * Math.exp(-event.deltaY * .01))), ratio = next / old;
        setPan(p => ({ x: x - (x - p.x) * ratio, y: y - (y - p.y) * ratio })); interaction.current.zoom = next; setZoom(next);
      } else if (interaction.current.zoom > 100) setPan(p => ({ x: p.x - event.deltaX, y: p.y - event.deltaY }));
      else if (!interaction.current.side) setSplit(old => Math.max(0, Math.min(100, old + event.deltaX / element.clientWidth * 100)));
    };
    element.addEventListener("wheel", wheel, { passive: false });
    return () => element.removeEventListener("wheel", wheel);
  }, []);
  const pathKey = paths.join("|");
  useEffect(() => {
    let alive = true;
    let raf = 0;
    const owned: FrameReader[] = [];
    if (movieCache.current?.operation !== operation.id || movieCache.current.api !== api)
      movieCache.current = { operation: operation.id, api, movies: new Map() };
    const cache = movieCache.current.movies;
    const run = async () => {
      try {
        const movies = await Promise.all(
          pathKey
            .split("|")
            .map((p) => compareMovie(cache, p, () => api.blob(p.replace("/v1/", "")).then(demux))),
        );
        if (!alive) return;
        if (
          movies.some(
            (m) =>
              Math.abs(movies[0].fps - m.fps) > 0.001 ||
              movies[0].samples.length !== m.samples.length,
          )
        )
          throw new Error(
            "The previews have different frame counts or frame rates.",
          );
        owned.push(...movies.map((m) => new FrameReader(m)));
        readers.current = owned;
        setCount(movies[0].samples.length);
        setFps(movies[0].fps);
        const draw = (now: number) => {
          if (!alive) return;
          const state = clock.current;
          if (state.playing)
            state.frame =
              state.anchorFrame +
              Math.floor(((now - state.anchor) / 1000) * movies[0].fps);
          if (state.frame >= movies[0].samples.length) {
            if (drawing.current.loop) state.frame %= movies[0].samples.length;
            else {
              state.frame = movies[0].samples.length - 1;
              state.playing = false;
              setPlaying(false);
            }
          }
          const pair = owned.map((r) => r.frame(state.frame));
          if (owned.some((r) => r.error)) {
            setError(owned.find((r) => r.error)!.error);
            return;
          }
          if (
            pair.every(
              (picture) =>
                picture &&
                Math.round((picture.timestamp / 1e6) * movies[0].fps) ===
                  state.frame,
            )
          ) {
            const a = pair[Math.min(drawing.current.left, pair.length - 1)]!,
              b = pair[Math.min(drawing.current.right, pair.length - 1)]!,
              element = canvas.current!;
            const width = a.displayWidth,
              height = a.displayHeight;
            const mode = drawing.current;
            const shown = mode.solo === null ? pair : [pair[mode.solo]!];
            const box = viewport.current?.getBoundingClientRect();
            let columns = 1, best = 0;
            if (mode.side && !mode.resultOnly && mode.solo === null) {
              for (let candidate = 1; candidate <= shown.length; candidate++) {
                const rows = Math.ceil(shown.length / candidate);
                const scale = Math.min((box?.width || 1200) / (candidate * width), (box?.height || 600) / (rows * height));
                if (scale > best) { best = scale; columns = candidate; }
              }
            }
            element.width = width * columns;
            element.height = height * (mode.side && !mode.resultOnly ? Math.ceil(shown.length / columns) : 1);
            element.dataset.columns = String(columns);
            element.dataset.rows = String(element.height / height);
            const ctx = element.getContext("2d")!;
            ctx.drawImage(a, 0, 0, width, height);
            if (mode.solo !== null) ctx.drawImage(pair[mode.solo]!, 0, 0, width, height);
            else if (mode.resultOnly) ctx.drawImage(b, 0, 0, width, height);
            else if (mode.side)
              pair.forEach((picture, i) =>
                ctx.drawImage(
                  picture!,
                  (i % columns) * width,
                  Math.floor(i / columns) * height,
                  width,
                  height,
                ),
              );
            else {
              ctx.save();
              ctx.beginPath();
              ctx.rect((width * mode.split) / 100, 0, width, height);
              ctx.clip();
              ctx.drawImage(b, 0, 0, width, height);
              ctx.restore();
            }
            element.dataset.frame = String(state.frame);
            element.dataset.syncDelta = String(
              Math.max(...pair.map((p) => p!.timestamp)) -
                Math.min(...pair.map((p) => p!.timestamp)),
            );
            element.dataset.frames = JSON.stringify(
              pair.map((p) => Math.round((p!.timestamp / 1e6) * movies[0].fps)),
            );
            setFrame(state.frame);
          }
          raf = requestAnimationFrame(draw);
        };
        raf = requestAnimationFrame(draw);
      } catch (e) {
        if (alive) setError((e as Error).message);
      }
    };
    void run();
    return () => {
      alive = false;
      cancelAnimationFrame(raf);
      owned.forEach((r) => r.close());
      readers.current = [];
    };
  }, [api, operation.id, pathKey]);
  const seek = (n: number) => {
    clock.current = {
      frame: Math.max(0, Math.min(count - 1, n)),
      playing: false,
      anchor: 0,
      anchorFrame: 0,
    };
    setPlaying(false);
    setFrame(clock.current.frame);
  };
  return (
    <div
      className={`compare ${full ? "is-full-window" : ""}`}
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key.toLowerCase() === "f" && !(e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement)) { e.preventDefault(); setFull(old => !old); }
        if (e.key === "Escape" && (full || solo !== null)) { e.preventDefault(); e.stopPropagation(); setFull(false); setSolo(null); }
        if (e.code === "Space" && !(e.target instanceof HTMLInputElement)) {
          e.preventDefault();
          e.currentTarget
            .querySelector<HTMLButtonElement>(".preview-play")
            ?.click();
        }
        if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
          e.preventDefault();
          seek(clock.current.frame + (e.key === "ArrowRight" ? 1 : -1));
        }
      }}
    >
      <p>
        {operation.result?.pipeline
          ? `Processed at ${operation.result.pipeline.fps.toFixed(2)} fps · `
          : ""}
        Previews {fps.toFixed(2)} fps
      </p>
      <div className="compare-labels">
        {labels.map((label) => (
          <strong key={label}>{label}</strong>
        ))}
      </div>
      <div
        className="canvas-viewport" ref={viewport}
        onDoubleClick={event => { const element = canvas.current!; const box = element.getBoundingClientRect(); const columns = Number(element.dataset.columns || 1), rows = Number(element.dataset.rows || 1); const index = Math.floor((event.clientY - box.top) / box.height * rows) * columns + Math.floor((event.clientX - box.left) / box.width * columns); setSolo(old => old === null ? Math.max(0, Math.min(labels.length - 1, index)) : null); setZoom(100); setPan({ x: 0, y: 0 }); }}
        onPointerUp={event => { pointers.current.delete(event.pointerId); gesture.current = null; }}
        onPointerCancel={event => { pointers.current.delete(event.pointerId); gesture.current = null; }}
        onPointerDown={(e) => {
          pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
          e.currentTarget.setPointerCapture(e.pointerId);
        }}
        onPointerMove={(e) => {
          if (e.pointerType === "touch") {
            pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
            const points = [...pointers.current.values()];
            if (points.length === 2) {
              const distance = Math.hypot(points[0].x - points[1].x, points[0].y - points[1].y), x = (points[0].x + points[1].x) / 2, y = (points[0].y + points[1].y) / 2;
              const previous = gesture.current;
              if (previous) { setZoom(old => Math.max(100, Math.min(800, old * distance / Math.max(1, previous.distance)))); setPan(p => ({ x: p.x + x - previous.x, y: p.y + y - previous.y })); }
              gesture.current = { distance, x, y }; return;
            }
          }
          if (zoom > 100 && e.buttons === 1)
            setPan((p) => ({ x: p.x + e.movementX, y: p.y + e.movementY }));
        }}
      >
        <canvas
          ref={canvas}
          aria-label="Original and enhanced synchronized preview"
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom / 100})`,
            imageRendering: zoom > 100 ? "pixelated" : "auto",
          }}
        />

      </div>
      {!side && !resultOnly && (
        <label>
          Comparison split
          <input
            type="range"
            min="0"
            max="100"
            value={split}
            onChange={(e) => setSplit(Number(e.target.value))}
          />
        </label>
      )}
      <label>
        Seek frame
        <input
          type="range"
          min="0"
          max={Math.max(0, count - 1)}
          value={frame}
          onChange={(e) => seek(Number(e.target.value))}
        />
      </label>
      <div className="toolbar">
        <ActionButton onClick={() => setFull(old => !old)}>Full window</ActionButton>
        {solo !== null && <ActionButton onClick={() => setSolo(null)}>All panes</ActionButton>}
        <ActionButton
          className="preview-play"
          disabled={!count}
          onClick={() => {
            const next = !playing;
            clock.current = {
              ...clock.current,
              playing: next,
              anchor: performance.now(),
              anchorFrame: clock.current.frame,
            };
            setPlaying(next);
          }}
        >
          {playing ? "Pause preview" : "Play preview"}
        </ActionButton>
        <ActionButton disabled={!count} onClick={() => seek(frame - 1)}>
          Previous frame
        </ActionButton>
        <ActionButton disabled={!count} onClick={() => seek(frame + 1)}>
          Next frame
        </ActionButton>
        <span className="preview-counter">
          Frame {frame + 1}/{count} ·{" "}
          {((operation.result?.start_seconds || 0) + frame / fps).toFixed(1)} /{" "}
          {((operation.result?.start_seconds || 0) + count / fps).toFixed(1)} s
        </span>
        <label className="check">
          <input
            type="checkbox"
            checked={side}
            onChange={(e) => {
              interaction.current.side = e.target.checked;
              interaction.current.zoom = e.target.checked ? 100 : 200;
              setSide(e.target.checked);
              setZoom(e.target.checked ? 100 : 200);
              setPan({ x: 0, y: 0 });
            }}
          />
          Side by side
        </label>
        {!operation.result?.items && <label className="check"><input type="checkbox" checked={resultOnly} onChange={event => setResultOnly(event.target.checked)} />Result only</label>}
        <label className="check">
          <input
            type="checkbox"
            checked={loop}
            onChange={(e) => setLoop(e.target.checked)}
          />
          Loop
        </label>
        {!side && labels.length > 2 && (
          <>
            {[
              ["Left", left, setLeft],
              ["Right", right, setRight],
            ].map(([label, selected, change]) => (
              <label key={String(label)}>
                {String(label)}
                <select
                  value={Number(selected)}
                  onChange={(e) =>
                    (change as (n: number) => void)(Number(e.target.value))
                  }
                >
                  {labels.map((name, i) => (
                    <option key={name} value={i}>
                      {name}
                    </option>
                  ))}
                </select>
              </label>
            ))}
          </>
        )}
        <div role="group" aria-label="Zoom" className="zoom-segments">
          <ActionButton aria-label="Zoom out" title="Zoom out" disabled={zoom <= 100} onClick={() => { const next = Math.max(100, zoom / 1.25); interaction.current.zoom = next; setZoom(next); }} />
          <ActionButton aria-label="Reset zoom" title="Reset zoom to 100%" className="zoom-reset" onClick={() => { interaction.current.zoom = 100; setZoom(100); setPan({ x: 0, y: 0 }); }}>{Math.round(zoom)}%</ActionButton>
          <ActionButton aria-label="Zoom in" title="Zoom in" disabled={zoom >= 800} onClick={() => { const next = Math.min(800, zoom * 1.25); interaction.current.zoom = next; setZoom(next); }} />
        </div>
      </div>
      <p className="muted">
        Arrow keys step one frame. Drag the zoomed picture to pan.
      </p>
      {error && (
        <Notice autoDismiss identity={error} dismiss={() => setError("")}>{error}</Notice>
      )}
    </div>
  );
}
function FirstLook({ api, image, name }: { api: Api; image: string; name: string }) {
  const [url, setUrl] = useState<string>();
  useEffect(() => {
    let alive = true, owned: string | undefined;
    void api.blob(image.replace(/^\/v1\//, "")).then(blob => {
      if (alive) { owned = URL.createObjectURL(blob); setUrl(owned); }
    }).catch(() => {});
    return () => { alive = false; if (owned) URL.revokeObjectURL(owned); };
  }, [api, image]);
  return <figure className="first-look">{url && <img src={url} alt={`${name} first look`} />}<figcaption>{name} · First look</figcaption></figure>;
}

function TrialDialogContent({
  api,
  value,
  operations,
  close,
  models = [],
  useModel,
  started = false,
  switchStandard,
}: {
  api: Api;
  value: { file: string; settings: Settings; media?: Media; job_id?: string };
  operations: Operation[];
  close(): void;
  models?: Model[];
  useModel?(
    key: "restore_model" | "interp_model" | "size_model",
    id: string,
  ): Promise<void> | void;
  started?: boolean;
  switchStandard?(): Promise<void> | void;
}) {
  const previous = operations.findLast(
    (o) =>
      o.kind === "compare" &&
      (value.job_id
        ? o.job_id === value.job_id
        : o.request?.file === value.file),
  );
  const [length, setLength] = useState(5);
  const [total, setTotal] = useState(value.media?.duration || 0);
  const [start, setStart] = useState(
    Math.max(0, (value.media?.duration || 0) / 2 - 2.5),
  );
  const [thumbnails, setThumbnails] = useState<string[]>([]);
  const [id, setId] = useState(previous?.id || "");
  const [initial, setInitial] = useState<Operation | undefined>(previous);
  const [error, setError] = useState("");
  const [category, setCategory] = useState(
    value.settings.preset === "standard" ? "cleanup" : "motion",
  );
  const key = category === "cleanup" ? "restore_model" : category === "size" ? "size_model" : "interp_model";
  const candidates = models.filter(
    (m) => m.task === (category === "cleanup" ? "restore" : category === "size" ? "size" : "interpolate"),
  );
  const [selected, setSelected] = useState<string[]>([
    value.settings.preset === "standard"
      ? value.settings.restore_model || "basicvsrpp-ntire21-decompress"
      : value.settings.interp_model || "rife-4.25",
  ]);
  const [chosen, setChosen] = useState(value.settings[key] || selected[0]);
  const [consent, setConsent] = useState<Model>();
  const [installing, setInstalling] = useState<string>();
  const [accepted, setAccepted] = useState(false);
  const [rangeReady, setRangeReady] = useState(false);
  const selectedKey = selected.join("|");
  const verifiedSelection = selected.every(id => models.some(model => model.id === id && model.weights_verified));
  const valueRef = useRef(value);
  valueRef.current = value;
  useEffect(() => setAccepted(false), [consent]);
  useEffect(() => {
    if (!installing || !models.some(model => model.id === installing && model.weights_verified)) return;
    setSelected(old => old.includes(installing) ? old : [...old.slice(0, 2), installing]);
    setInstalling(undefined);
  }, [installing, models]);
  useEffect(() => {
    if (!rangeReady || !total || !selectedKey || !verifiedSelection) return;
    const abort = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const op = await api.call<Operation>("compare", "POST", {
          ...valueRef.current, start: Math.min(start, Math.max(0, total - length)),
          seconds: length, models: selectedKey.split("|"),
        }, abort.signal);
        if (!abort.signal.aborted) { setId(op.id); setInitial(op); setError(""); }
      } catch (error) { if (!abort.signal.aborted) setError((error as Error).message); }
    }, 800);
    return () => { clearTimeout(timer); abort.abort(); };
  }, [api, start, length, selectedKey, total, rangeReady, verifiedSelection]);
  const operation = operations.find((o) => o.id === id) || initial;
  useEffect(() => {
    let alive = true;
    void api
      .call<{ thumbnails: string[]; duration: number }>(
        "trial/thumbnails",
        "POST",
        { file: value.file },
      )
      .then((r) => {
        if (alive) {
          setThumbnails(r.thumbnails);
          setTotal(r.duration);
          void api.call<{ start: number }>("compare/range", "POST", { file: value.file, job_id: value.job_id })
            .then(range => { if (alive) { setStart(range.start); setRangeReady(true); } })
            .catch(error => { if (alive) setError(error.message); });
        }
      })
      .catch((e) => {
        if (alive) setError(e.message);
      });
    return () => {
      alive = false;
    };
  }, [api, value.file]);
  return (
    <div className="modal-shade compare-full-window">
      <div
        className="dialog trial-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="trial-title"
      >
        <div className="page-heading">
          <h2 id="trial-title">Compare models — {filename(value.file)}</h2>
          <ActionButton
            onClick={async () => {
              close();
            }}
          >
            Back
          </ActionButton>
        </div>
        {value.settings.preset === "fast" && <div className="card fast-panel"><h3>Fast does not clean up.</h3><ActionButton disabled={started || !switchStandard} onClick={async () => { try { await switchStandard?.(); setCategory("cleanup"); setSelected(["basicvsrpp-ntire21-decompress"]); } catch (error) { setError((error as Error).message); } }}>Switch to Standard</ActionButton><ActionButton onClick={() => { setCategory("motion"); setSelected([value.settings.interp_model || "rife-4.25"]); }}>Compare smoother motion instead</ActionButton></div>}
        <details className="compare-controls" open={!operation?.result?.original}><summary>Models and preview range</summary>
        <div className="thumbnails range-track" onKeyDown={event => { if (["ArrowLeft", "ArrowRight"].includes(event.key)) { event.preventDefault(); setStart(old => Math.max(0, Math.min(total-length, old + (event.key === "ArrowRight" ? 1 : -1) * (event.shiftKey ? 5 : 1)))); } }} tabIndex={0} aria-label="Preview range">
          <span className="range-box" aria-hidden="true" style={{ left: `${total ? start / total * 100 : 0}%`, width: `${total ? Math.min(length, total) / total * 100 : 100}%` }} />
          {thumbnails.map((src, i) => (
            <img
              src={src}
              key={i}
              alt={`Preview at ${((i * total) / 7).toFixed(1)} seconds`}
              onClick={() => setStart(Math.min(Math.max(0, total - length), i * total / 7))}
            />
          ))}
        </div>
        <label>
          Start: {start.toFixed(1)} s
          <input
            type="range"
            min="0"
            max={Math.max(0, total - length)}
            step="0.1"
            value={Math.min(start, Math.max(0, total - length))}
            onChange={(e) => setStart(Number(e.target.value))}
            onKeyDown={event => {
              if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
              event.preventDefault();
              setStart(old => Math.max(0, Math.min(total - length, old + (event.key === "ArrowRight" ? 1 : -1) * (event.shiftKey ? 5 : 1))));
            }}
          />
        </label>
        <div className="filter-pills">
          <label>
            Comparing
            <select
              value={category}
              onChange={(e) => {
                const next = e.target.value;
                setCategory(next);
                const model = models.find(
                  (m) =>
                    m.weights_verified &&
                    m.task === (next === "cleanup" ? "restore" : next === "size" ? "size" : "interpolate"),
                );
                setSelected(model ? [model.id] : []);
                setChosen(
                  next === "cleanup"
                    ? value.settings.restore_model ||
                        "basicvsrpp-ntire21-decompress"
                    : next === "size" ? value.settings.size_model || model?.id || "" : value.settings.interp_model || "rife-4.25",
                );
              }}
            >
              <option
                value="cleanup"
                disabled={value.settings.preset !== "standard"}
              >
                Cleanup
              </option>
              <option value="motion">Smoother motion</option>
              <option value="size" disabled={!models.some(model => model.task === "size" && model.weights_verified)}>
                Bigger picture
              </option>
            </select>
          </label>
          <span className="badge">Original</span>
          {candidates.map((m) => (
            <ActionButton
              key={m.id}
              icon={m.weights_verified ? selected.includes(m.id) ? Check : Layers : Download}
              title={m.catalog?.title || m.display_name}
              aria-pressed={selected.includes(m.id)}
              onClick={() =>
                m.weights_verified
                  ? setSelected((old) =>
                      old.includes(m.id)
                        ? old.filter((id) => id !== m.id)
                      : [...old.slice(0, 2), m.id],
                    )
                  : setConsent(m)
              }
            >
              {m.catalog?.title || m.display_name}
              {m.weights_verified ? "" : " · installs model weights"}
            </ActionButton>
          ))}
        </div>
        <div className="toolbar">
          <label>
            Length
            <select
              value={length}
              onChange={(e) => setLength(Number(e.target.value))}
            >
              {[3, 5, 10].map((n) => (
                <option key={n} value={n}>
                  {n} seconds
                </option>
              ))}
            </select>
          </label>
          {operation?.state === "failed" && <ActionButton
            className="primary"
            disabled={
              !total ||
              !selected.length ||
              selected.some(
                (id) => !models.some((m) => m.id === id && m.weights_verified),
              )
            }
            onClick={async () => {
              try {
                const op = await api.call<Operation>("compare", "POST", {
                  ...value,
                  start: Math.min(start, Math.max(0, total - length)),
                  seconds: length,
                  models: selected,
                });
                setId(op.id);
                setInitial(op);
                setError("");
              } catch (e) {
                setError((e as Error).message);
              }
            }}
          >
            Try again
          </ActionButton>}
        </div>
        <p className="muted">
          A busy engine starts this after its current step, including outside
          your hours.
        </p>
        </details>
        {operation && operation.state !== "done" && (
          <OperationStatus
            operation={operation}
            cancel={() => void api.call(`operations/${id}/cancel`, "POST", {})}
          />
        )}
        {operation?.state === "done" && <p className="muted">Compare: done</p>}
        {operation?.state !== "done" && <div className="first-looks">
          {operation?.result?.first_looks?.map(look => <FirstLook key={look.id} api={api} image={look.image} name={look.id === "original" ? "Original" : models.find(model => model.id === look.id)?.catalog?.title || look.id} />)}
        </div>}
        {operation?.result?.original && (
          <Compare api={api} operation={operation} />
        )}
        <details className="compare-choice"><summary>Use a model</summary><div className="model-grid">
          {selected.map((id) => {
            const model = models.find((m) => m.id === id);
            const item = operation?.result?.items?.find((m) => m.id === id);
            const modelProgress = operation?.result?.model_progress?.[id];
            return (
              <article className="card" key={id}>
                <h3>{model?.catalog?.title || model?.display_name || id}</h3>
                <p>{model?.catalog?.description || model?.catalog?.summary}</p>
                <p role="status">{item ? "Ready" : operation?.state === "waiting" ? operation.phase : operation?.state === "failed" ? "Problem" : modelProgress ? `Making preview ${Math.round(modelProgress.percent)}% · ${duration(modelProgress.remaining_seconds)} left` : "Waiting"}</p>
                <p>
                  {item?.projected_whole_file_seconds === null ? `Speed unknown for this video · ${item.fps.toFixed(2)} fps` : item
                    ? `About ${duration(item.projected_whole_file_seconds)} for this video · ${item.fps.toFixed(2)} fps`
                    : "Measuring speed…"}
                </p>
                <ActionButton
                  disabled={started || !useModel || !item || chosen === id}
                  title={
                    started
                      ? "Already started. Remove it and add it again to use another model."
                      : undefined
                  }
                  onClick={async () => {
                    try {
                      await useModel?.(key, id);
                      setChosen(id);
                    } catch (e) {
                      setError((e as Error).message);
                    }
                  }}
                >
                  {chosen === id ? "Chosen" : "Use this"}
                </ActionButton>
                <ActionButton
                  onClick={async () => {
                    try {
                      await api.call("settings", "PUT", { [key]: id });
                    } catch (e) {
                      setError((e as Error).message);
                    }
                  }}
                >
                  Make it my default
                </ActionButton>
              </article>
            );
          })}
        </div></details>
        {consent && (
          <div className="modal-shade">
            <div className="dialog" role="dialog" aria-modal="true">
              <h3>Install {consent.catalog?.title || consent.display_name}?</h3>
              <p>Licence: {consent.licence}</p>
              <p className="break">Source: {consent.weights.url}</p>
              {consent.publisher_url && <a href={consent.publisher_url} target="_blank" rel="noreferrer">Model publisher’s page</a>}
              <label className="check"><input type="checkbox" checked={accepted} onChange={event => setAccepted(event.target.checked)} />I accept this licence</label>
              <ActionButton onClick={() => setConsent(undefined)}>Cancel</ActionButton>
              <ActionButton
                disabled={!accepted}
                onClick={async () => {
                  try {
                    await api.call(`models/${consent.id}/download`, "POST", {
                      agree: true,
                      licence: consent.licence,
                    });
                    setInstalling(consent.id);
                    setConsent(undefined);
                  } catch (e) {
                    setError((e as Error).message);
                  }
                }}
              >
                Accept licence and download
              </ActionButton>
            </div>
          </div>
        )}
        {error && (
          <Notice autoDismiss identity={error} dismiss={() => setError("")}>
            {error}
          </Notice>
        )}
      </div>
    </div>
  );
}

export function TrialDialog(props: Parameters<typeof TrialDialogContent>[0]) {
  return <ErrorBoundary scope="Compare"><TrialDialogContent {...props} /></ErrorBoundary>;
}
