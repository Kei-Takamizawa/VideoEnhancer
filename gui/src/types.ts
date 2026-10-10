export type Settings = {
  preset: string;
  codec: string;
  short_side: string | number;
  fps: string;
  output_folder: string;
  start_with_windows: boolean;
  theme: string;
  log_folder: string;
  advanced: Record<string, number>;
  backend?: string;
  restore_model?: string;
};
export type Media = {
  display_width: number;
  display_height: number;
  cfr_fps: string;
  duration: number;
  frame_count: number;
};
export type Estimate = {
  seconds: number;
  low: number;
  high: number;
  calibrated: boolean;
  finish?: string | null;
};
export type Job = {
  id: string;
  state: string;
  input: string;
  output: string;
  settings: Settings;
  media: Media;
  error?: string;
  estimate: Estimate;
  eta?: string;
  progress_percent: number;
  phase: string;
  step: string;
  step_percent: number;
  segment: number;
  segments: number;
  fps?: number;
  log: string;
  overrun_seconds?: number;
  finished_at?: string;
  took_seconds?: number;
  output_bytes?: number;
  starts?: string;
  preview_ready?: boolean;
};
export type Operation = {
  id: string;
  kind: string;
  state: string;
  phase: string;
  percent?: number;
  error?: string;
  job_id?: string;
  request?: { file?: string };
  result?: {
    pipeline?: { fps: number };
    output_fps?: number;
    preview?: { original: string; enhanced: string };
    sha256?: string;
    bytes?: number;
    weights_verified?: boolean;
  };
};
export type Queue = {
  jobs: Job[];
  completion: string | null;
  operations: Operation[];
};
export type Health = {
  version: string;
  gpu?: string;
  driver?: string;
  vram_bytes?: number;
  av1_supported?: boolean;
  engine_state: string;
  job_id?: string;
  next_change?: string;
  next_change_kind: string;
  last_error?: { time: string; job_id: string | null; message: string };
  home: string;
  smart_app_control: { status: string; blocked: boolean; message?: string };
};
export type Window = { start: string; end: string };
export type Schedule = {
  schema_version: number;
  timezone?: string;
  enabled: boolean;
  weekly: (Window & { days: string[] })[];
  exceptions: { date: string; windows: Window[] | "off" }[];
  override_until?: string | null;
};
export type Plan = {
  timezone: string;
  days: {
    date: string;
    windows: Window[];
    run_hours: number;
    jobs: {
      job_id: string;
      start_percent: number;
      end_percent: number;
      completion?: string;
    }[];
  }[];
  timeline: (Window & {
    job_id: string;
    phase: string;
    overrun_seconds?: number;
  })[];
  jobs: { job_id: string; completion: string | null }[];
};
export type Model = {
  id: string;
  display_name: string;
  task: string;
  architecture: string;
  licence: string;
  commercial_use_allowed: boolean;
  size_bytes: number;
  builtin: boolean;
  weights_verified: boolean;
  weights: { url?: string; sha256: string };
};
export type Connection = { base_url: string; token: string };
export interface Desktop {
  connection(): Promise<Connection>;
  files(kind: "videos" | "folder"): Promise<string[]>;
  openFolder(folder: string): Promise<void>;
  play(file: string): Promise<void>;
  copy(text: string): Promise<void>;
  filePath(file: File): string;
}
declare global {
  interface Window {
    desktop: Desktop;
  }
}
