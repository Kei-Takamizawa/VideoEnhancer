import { useEffect, useRef, useState } from "react";
import { createFile } from "mp4box";
import type { Sample } from "mp4box";
import type { Api } from "./api";
import { filename } from "./api";
import type { Media, Operation, Settings } from "./types";
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
  const [side, setSide] = useState(false);
  const [zoom, setZoom] = useState(100);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [error, setError] = useState("");
  const drawing = useRef({ split, side });
  drawing.current = { split, side };
  useEffect(() => {
    let alive = true;
    let raf = 0;
    const owned: FrameReader[] = [];
    const run = async () => {
      try {
        const paths = operation.result!.preview!;
        const movies = await Promise.all(
          [paths.original, paths.enhanced].map((p) =>
            api.blob(p.replace("/v1/", "")).then(demux),
          ),
        );
        if (!alive) return;
        if (
          Math.abs(movies[0].fps - movies[1].fps) > 0.001 ||
          movies[0].samples.length !== movies[1].samples.length
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
              (state.anchorFrame +
                Math.floor(((now - state.anchor) / 1000) * movies[0].fps)) %
              movies[0].samples.length;
          const pair = owned.map((r) => r.frame(state.frame));
          if (owned.some((r) => r.error)) {
            setError(owned.find((r) => r.error)!.error);
            return;
          }
          if (
            pair[0] &&
            pair[1] &&
            Math.abs(pair[0].timestamp - pair[1].timestamp) <=
              1e6 / movies[0].fps
          ) {
            const a = pair[0],
              b = pair[1],
              element = canvas.current!;
            const width = a.displayWidth,
              height = a.displayHeight;
            const mode = drawing.current;
            element.width = width * (mode.side ? 2 : 1);
            element.height = height;
            const ctx = element.getContext("2d")!;
            ctx.drawImage(a, 0, 0, width, height);
            if (mode.side) ctx.drawImage(b, width, 0, width, height);
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
              Math.abs(a.timestamp - b.timestamp),
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
  }, [api, operation.id]);
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
        if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
          e.preventDefault();
          seek(clock.current.frame + (e.key === "ArrowRight" ? 1 : -1));
        }
      }}
    >
      <p>
        Processed at {operation.result?.pipeline?.fps.toFixed(2)} fps · previews{" "}
        {fps.toFixed(2)} fps
      </p>
      <div className="compare-labels">
        <strong>Original</strong>
        <strong>Enhanced</strong>
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
          Frame {frame + 1}/{count} · Loop
        </span>
        <label className="check">
          <input
            type="checkbox"
            checked={side}
            onChange={(e) => setSide(e.target.checked)}
          />
          Side by side
        </label>
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
}: {
  api: Api;
  value: { file: string; settings: Settings; media?: Media; job_id?: string };
  operations: Operation[];
  close(): void;
}) {
  const previous = operations.findLast(
    (o) =>
      o.kind === "trial" &&
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
          <h2 id="trial-title">Trial — {filename(value.file)}</h2>
          <button onClick={close}>Close</button>
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
              !total
            }
            onClick={async () => {
              try {
                const op = await api.call<Operation>("trial", "POST", {
                  ...value,
                  start: Math.min(start, Math.max(0, total - length)),
                  seconds: length,
                });
                setId(op.id);
                setInitial(op);
                setError("");
              } catch (e) {
                setError((e as Error).message);
              }
            }}
          >
            Render trial
          </button>
        </div>
        <p className="muted">
          A busy engine runs this between segments. A trial may run at most{" "}
          {length} seconds past the end of operating hours.
        </p>
        {operation && (
          <OperationStatus
            operation={operation}
            cancel={() => void api.call(`operations/${id}/cancel`, "POST", {})}
          />
        )}
        {operation?.state === "done" && operation.result?.preview && (
          <Compare api={api} operation={operation} />
        )}{" "}
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
      </div>
    </div>
  );
}
