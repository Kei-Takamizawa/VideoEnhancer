import { useEffect, useRef, useState } from "react";
import { createFile } from "mp4box";
import type { Sample } from "mp4box";
import type { Api } from "./api";
import { filename } from "./api";
import type { Media, Model, Operation, Settings } from "./types";
import { OperationStatus } from "./Pages";

type Movie = { config: VideoDecoderConfig; samples: Sample[]; fps: number };
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
  const readers = useRef<FrameReader[]>([]);
  const clock = useRef({ frame: 0, playing: false, anchor: 0, anchorFrame: 0 });
  const [count, setCount] = useState(0);
  const [fps, setFps] = useState(30);
  const [frame, setFrame] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [split, setSplit] = useState(50);
  const [side, setSide] = useState(!!operation.result?.items);
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
  const drawing = useRef({ split, side, left, right, loop, labels });
  drawing.current = { split, side, left, right, loop, labels };
  const pathKey = paths.join("|");
  useEffect(() => {
    let alive = true;
    let raf = 0;
    const owned: FrameReader[] = [];
    const run = async () => {
      try {
        const movies = await Promise.all(
          pathKey
            .split("|")
            .map((p) => api.blob(p.replace("/v1/", "")).then(demux)),
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
            const columns = mode.side
              ? width > height
                ? Math.min(2, pair.length)
                : pair.length
              : 1;
            element.width = width * columns;
            element.height =
              height * (mode.side ? Math.ceil(pair.length / columns) : 1);
            const ctx = element.getContext("2d")!;
            ctx.drawImage(a, 0, 0, width, height);
            if (mode.side)
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
            if (mode.side) {
              ctx.font = "24px Segoe UI";
              pair.forEach((_, i) => {
                const x = (i % columns) * width,
                  y = Math.floor(i / columns) * height;
                ctx.fillStyle = "rgba(0,0,0,0.7)";
                ctx.fillRect(
                  x,
                  y,
                  Math.min(width, ctx.measureText(mode.labels[i]).width + 20),
                  34,
                );
                ctx.fillStyle = "white";
                ctx.fillText(mode.labels[i], x + 10, y + 25);
              });
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
      className="compare"
      tabIndex={0}
      onKeyDown={(e) => {
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
        className="canvas-viewport"
        onPointerDown={(e) => {
          if (zoom > 100) e.currentTarget.setPointerCapture(e.pointerId);
        }}
        onPointerMove={(e) => {
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
      {!side && (
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
        <button
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
        </button>
        <button disabled={!count} onClick={() => seek(frame - 1)}>
          Previous frame
        </button>
        <button disabled={!count} onClick={() => seek(frame + 1)}>
          Next frame
        </button>
        <span>
          Frame {frame + 1}/{count} ·{" "}
          {((operation.result?.start_seconds || 0) + frame / fps).toFixed(1)} /{" "}
          {((operation.result?.start_seconds || 0) + count / fps).toFixed(1)} s
        </span>
        <label className="check">
          <input
            type="checkbox"
            checked={side}
            onChange={(e) => {
              setSide(e.target.checked);
              setZoom(e.target.checked ? 100 : 200);
              setPan({ x: 0, y: 0 });
            }}
          />
          Side by side
        </label>
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
        <label>
          Zoom
          <select
            value={zoom}
            onChange={(e) => {
              setZoom(Number(e.target.value));
              setPan({ x: 0, y: 0 });
            }}
          >
            {[100, 200, 300, 400].map((n) => (
              <option key={n} value={n}>
                {n}%
              </option>
            ))}
          </select>
        </label>
      </div>
      <p className="muted">
        Arrow keys step one frame. Drag the zoomed picture to pan.
      </p>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
    </div>
  );
}
export function TrialDialog({
  api,
  value,
  operations,
  close,
  models = [],
  useModel,
  started = false,
}: {
  api: Api;
  value: { file: string; settings: Settings; media?: Media; job_id?: string };
  operations: Operation[];
  close(): void;
  models?: Model[];
  useModel?(
    key: "restore_model" | "interp_model",
    id: string,
  ): Promise<void> | void;
  started?: boolean;
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
  const key = category === "cleanup" ? "restore_model" : "interp_model";
  const candidates = models.filter(
    (m) => m.task === (category === "cleanup" ? "restore" : "interpolate"),
  );
  const [selected, setSelected] = useState<string[]>([
    value.settings.preset === "standard"
      ? value.settings.restore_model || "basicvsrpp-ntire21-decompress"
      : value.settings.interp_model || "rife-4.25",
  ]);
  const [chosen, setChosen] = useState(value.settings[key] || selected[0]);
  const [consent, setConsent] = useState<Model>();
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
          setStart(Math.max(0, r.duration / 2 - 2.5));
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
    <div className="modal-shade">
      <div
        className="dialog trial-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="trial-title"
      >
        <div className="page-heading">
          <h2 id="trial-title">Compare models — {filename(value.file)}</h2>
          <button
            onClick={async () => {
              close();
            }}
          >
            Back
          </button>
        </div>
        <div className="thumbnails">
          {thumbnails.map((src, i) => (
            <img
              src={src}
              key={i}
              alt={`Preview at ${((i * total) / 7).toFixed(1)} seconds`}
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
                    m.task === (next === "cleanup" ? "restore" : "interpolate"),
                );
                setSelected(model ? [model.id] : []);
                setChosen(
                  next === "cleanup"
                    ? value.settings.restore_model ||
                        "basicvsrpp-ntire21-decompress"
                    : value.settings.interp_model || "rife-4.25",
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
              <option value="size" disabled>
                Bigger picture · Standard resize
              </option>
            </select>
          </label>
          <span className="badge">Original</span>
          {candidates.map((m) => (
            <button
              key={m.id}
              aria-pressed={selected.includes(m.id)}
              disabled={
                m.weights_verified &&
                !selected.includes(m.id) &&
                selected.length >= 3
              }
              onClick={() =>
                m.weights_verified
                  ? setSelected((old) =>
                      old.includes(m.id)
                        ? old.filter((id) => id !== m.id)
                        : [...old, m.id],
                    )
                  : setConsent(m)
              }
            >
              {m.weights_verified
                ? selected.includes(m.id)
                  ? "✓ "
                  : ""
                : "+ "}
              {m.catalog?.title || m.display_name}
              {m.weights_verified ? "" : " · installs model weights"}
            </button>
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
          <button
            className="primary"
            disabled={
              operation?.state === "waiting" ||
              operation?.state === "running" ||
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
            Compare selected models
          </button>
        </div>
        <p className="muted">
          A busy engine starts this after its current step, including outside
          your hours.
        </p>
        {operation && operation.state !== "done" && (
          <OperationStatus
            operation={operation}
            cancel={() => void api.call(`operations/${id}/cancel`, "POST", {})}
          />
        )}
        {operation?.state === "done" && <p className="muted">Compare: done</p>}
        {operation?.result?.original && (
          <Compare api={api} operation={operation} />
        )}
        <div className="model-grid">
          {selected.map((id) => {
            const model = models.find((m) => m.id === id);
            const item = operation?.result?.items?.find((m) => m.id === id);
            return (
              <article className="card" key={id}>
                <h3>{model?.catalog?.title || model?.display_name || id}</h3>
                <p>{model?.catalog?.description}</p>
                <p>
                  {item
                    ? `About ${Math.floor(item.projected_whole_file_seconds / 3600)} h ${Math.round((item.projected_whole_file_seconds % 3600) / 60)} m for this video · ${item.fps.toFixed(2)} fps`
                    : "Measuring speed…"}
                </p>
                <button
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
                </button>
                <button
                  onClick={async () => {
                    try {
                      await api.call("settings", "PUT", { [key]: id });
                    } catch (e) {
                      setError((e as Error).message);
                    }
                  }}
                >
                  Make it my default
                </button>
              </article>
            );
          })}
        </div>
        {consent && (
          <div className="modal-shade">
            <div className="dialog" role="dialog" aria-modal="true">
              <h3>Install {consent.catalog?.title || consent.display_name}?</h3>
              <p>Licence: {consent.licence}</p>
              <p className="break">Source: {consent.weights.url}</p>
              <button onClick={() => setConsent(undefined)}>Cancel</button>
              <button
                onClick={async () => {
                  try {
                    await api.call(`models/${consent.id}/download`, "POST", {
                      agree: true,
                      licence: consent.licence,
                    });
                    setConsent(undefined);
                  } catch (e) {
                    setError((e as Error).message);
                  }
                }}
              >
                Accept licence and download
              </button>
            </div>
          </div>
        )}
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
      </div>
    </div>
  );
}
