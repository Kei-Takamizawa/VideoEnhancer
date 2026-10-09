# Local engine API v1

Start `ve serve` with the same `VE_HOME` as the CLI. It binds only to
127.0.0.1 on a randomly assigned port. A second service for that home exits with
the existing port. `%VE_HOME%/serve.json` contains `port`, `pid`, `token`; Windows
ACLs restrict it to the current user (POSIX CPU test hosts use mode 0600).
Quit/shutdown aborts the active segment consistently and leaves queued work
resumable. The CLI and service share the same JobStore and controller lock.

Every endpoint requires `Authorization: Bearer <token>`. Host must be the exact
127.0.0.1:port. Allowed origins are `app://videoenhancer` and the development
renderer `http://127.0.0.1:5173`; null and foreign origins are rejected. Local
non-browser tools may omit Origin; cross-site browser requests without an allowed
origin are rejected. Tokens are not URL parameters. OPTIONS only provides local
preflight; it does not authorize another origin. These checks protect against
web-origin requests and rebinding, not malware running as the same Windows user.

Use this PowerShell helper for the examples below:

```powershell
$veHome = "$env:LOCALAPPDATA\VideoEnhancer" # or your VE_HOME
$connection = Get-Content "$veHome\serve.json" -Raw | ConvertFrom-Json
$base = "http://127.0.0.1:$($connection.port)/v1"
$headers = @{ Authorization = "Bearer $($connection.token)" }
function Invoke-VeApi($route, $method = 'GET', $body = $null) {
  $params = @{ Uri = "$base/$route"; Method = $method; Headers = $headers }
  if ($null -ne $body) { $params.Body = $body | ConvertTo-Json -Depth 20; $params.ContentType = 'application/json' }
  Invoke-RestMethod @params
}
```

Requests and responses are JSON except SSE and preview files. Maximum request
body is 1 MB. Errors return `{ "error": "explanation" }`: 401 missing/wrong token,
403 origin/host, 404 missing job/endpoint/file, 400 invalid request, 409 execution
failure, 413 unsupported/oversized body. Routes below omit the `/v1/` prefix.

## Health, queue and estimates

| Method / route | Response or effect | Example |
| --- | --- | --- |
| GET health | Engine version, environment versions, GPU/driver/VRAM, Smart App Control, engine state, current job, next change and last error | `Invoke-VeApi 'health'` |
| GET queue | Compact durable jobs with phase/step/percent, segments, fps, ETA, estimates; all-job completion and auxiliary operations | `Invoke-VeApi 'queue'` |
| POST queue | Return a durable preparing manifest immediately; analyze and validate selected weights in a background thread, then queue or fail the job | `Invoke-VeApi 'queue' 'POST' @{file='C:\Video\clip.mp4'; settings=@{preset='standard'; codec='hevc'; short_side=1080; fps='2x'}; output_folder='C:\Video\enhanced'}` |
| POST queue/{id}/move | Reorder using one-based position | `Invoke-VeApi 'queue/JOB_ID/move' 'POST' @{position=1}` |
| POST queue/{id}/pause | Persist paused state; active segment aborts | `Invoke-VeApi 'queue/JOB_ID/pause' 'POST' @{}` |
| POST queue/{id}/resume | Persist queued state, respecting the schedule | `Invoke-VeApi 'queue/JOB_ID/resume' 'POST' @{}` |
| POST queue/{id}/cancel | Persist cancelled state; active segment aborts | `Invoke-VeApi 'queue/JOB_ID/cancel' 'POST' @{}` |
| DELETE queue/{id} | Remove done/cancelled/failed job and associated previews after workers stop; keep output | `Invoke-VeApi 'queue/JOB_ID' 'DELETE'` |
| GET queue/{id}/log | Last 64 KB of job log as `{text}` | `Invoke-VeApi 'queue/JOB_ID/log'` |
| POST processing | Tray-wide pause/resume of queued/running or paused jobs | `Invoke-VeApi 'processing' 'POST' @{paused=$true}` |
| POST estimate | Probe metadata; Standard/Fast seconds/low/high/calibration and finish under queue/schedule; HDR/SAC/disk warnings and exact free/required bytes | `Invoke-VeApi 'estimate' 'POST' @{file='C:\Video\clip.mp4'; settings=@{short_side=1080; fps='2x'}}` |
| GET plan?scenario=expected | Existing engine planner, 120-day horizon: daily windows/run hours/job percentages, timeline, completion. best/worst apply estimate bounds to planner copies | `Invoke-VeApi 'plan?scenario=worst'` |

Output defaults to the configured folder, otherwise the source's `enhanced`
subfolder. Explicit `output` is also accepted by queue requests (CPU test fixtures
use this). CPU backend and existing engine fixture presets are supported by the
API; the desktop offers only Standard and Fast. No endpoint runs full-quality
reporting. Opening folders and copying details are desktop actions.

## Schedule and settings

| Method / route | Effect | Example |
| --- | --- | --- |
| GET schedule | Read the engine's saved weekly schedule/exceptions/override | `Invoke-VeApi 'schedule'` |
| PUT schedule | Validate and atomically save; quarter-hour times, minimum 15 minutes, crossing midnight; overlapping allowed intervals merge in the scheduler | `Invoke-VeApi 'schedule' 'PUT' @{enabled=$true; weekly=@(@{days=@('mon','tue','wed','thu','fri'); start='22:00'; end='08:00'}); exceptions=@(@{date='2026-10-12'; windows='off'})}` |
| POST schedule/preview | Validate unsaved schedule without saving; next window plus entire queue plan | `Invoke-VeApi 'schedule/preview' 'POST' @{enabled=$false; weekly=@(); exceptions=@()}` |
| POST schedule/override | until=null clears; job-complete overrides through current job; ISO timestamp sets deadline | `Invoke-VeApi 'schedule/override' 'POST' @{until='job-complete'}` |
| GET settings | Saved preferences with defaults | `Invoke-VeApi 'settings'` |
| PUT settings | Validate/save partial or complete preferences; new jobs use defaults | `Invoke-VeApi 'settings' 'PUT' @{theme='dark'; preset='standard'; codec='hevc'; short_side=1080; fps='2x'; output_folder='C:\Video\enhanced'; start_with_windows=$false; log_folder='C:\Video\logs'; advanced=@{clip_length=15; clip_overlap=2; interpolation_safety_threshold=0.2}}` |

Schedule timezone defaults to the host's IANA timezone; API clients can specify
`timezone`. Exceptions use `windows='off'` or an array of `{start,end}`. Electron
applies `start_with_windows` via login-item APIs; the service only persists it.
Theme is system/dark/light. Folder preferences must be absolute. Advanced clip
length/overlap and threshold validation returns plain-English errors.

## Auxiliary work, trials and models

Auxiliary operations return `{id,kind,state,phase,request,job_id,...}` immediately.
States are waiting/running/done/failed/cancelled. They share the controller lease
and execute between segments, so two GPU pipelines cannot overlap. Results and
errors appear through GET operations and SSE; active work is isolated in a
cancellable child process. Pending operation state is session-local; after a
service restart submit a new trial/calibration. Completed job-associated previews
are still removed when their job is removed.

| Method / route | Effect | Example |
| --- | --- | --- |
| POST trial/thumbnails | Eight source thumbnails as JPEG data URLs and source duration | `Invoke-VeApi 'trial/thumbnails' 'POST' @{file='C:\Video\clip.mp4'}` |
| POST trial | Existing real trial pipeline, start in seconds, length 3/5/10, settings; optional job_id updates that job's speed correction | `Invoke-VeApi 'trial' 'POST' @{file='C:\Video\clip.mp4'; start=30; seconds=5; settings=@{preset='standard'; short_side=1080; fps='2x'}; job_id='JOB_ID'}` |
| GET operations/{id} | State, result and error of auxiliary work | `Invoke-VeApi 'operations/OP_ID'` |
| POST operations/{id}/cancel | Cancel waiting or active operation | `Invoke-VeApi 'operations/OP_ID/cancel' 'POST' @{}` |
| GET operations/{id}/files/original | Matching resized source H.264 8-bit MP4; requires done trial and token | `Invoke-WebRequest "$base/operations/OP_ID/files/original" -Headers $headers -OutFile 'C:\Video\original-preview.mp4'` |
| GET operations/{id}/files/enhanced | Enhanced H.264 8-bit MP4; same restricted fetch | `Invoke-WebRequest "$base/operations/OP_ID/files/enhanced" -Headers $headers -OutFile 'C:\Video\enhanced-preview.mp4'` |
| POST calibrate | Existing `ve bench --calibrate` speed calibration (no all-model benchmark) | `Invoke-VeApi 'calibrate' 'POST' @{}` |
| GET models | Manifest/licence/commercial/task/architecture, installed size, built-in flag and hash verification | `Invoke-VeApi 'models'` |
| POST models | Add local model.json and weights with existing registry validation | `Invoke-VeApi 'models' 'POST' @{folder='C:\MyModels\my-model'}` |
| DELETE models/{id} | Remove user-added model; built-ins are refused | `Invoke-VeApi 'models/my-model' 'DELETE'` |
| POST models/{id}/download | Built-in only: exact licence string and explicit agree=true required; timestamp/source/licence recorded in consent/{id}.json before work starts | `Invoke-VeApi 'models/basicvsrpp-ntire21-decompress/download' 'POST' @{agree=$true; licence='EXACT_LICENCE_FROM_GET_MODELS'}` |
| POST models/{id}/verify | SHA-256 revalidation without downloading | `Invoke-VeApi 'models/MODEL_ID/verify' 'POST' @{}` |
| POST shutdown | Gracefully stop controller/children, then close HTTP; discovery removed | `Invoke-VeApi 'shutdown' 'POST' @{}` |

Trial previews are libx264 CRF 16/yuv420p. The source uses the trial pipeline's
same resize stage; both previews use the same output fps. Allowed-hour overrun
is bounded by the requested excerpt length; reaching that deadline cancels work.
Verification/download results include `sha256`, `bytes`, `weights_verified`.
Calibration/model progress is reported by state/phase; its indicator is
indeterminate when the underlying CLI operation provides no percentage.

## Events

GET events is `text/event-stream`, authenticated by the same headers. It emits
an update snapshot containing `{queue,health,plan}` when state changes (checked
each second), including job/segment progress, fps, ETA, planner changes and
errors. It sends `: heartbeat` at least every 10 seconds while connected.

```powershell
curl.exe -N -H "Authorization: Bearer $($connection.token)" "$base/events"
```

Example event structure (numbers are illustrative):

```text
event: update
data: {"queue":{"jobs":[],"operations":[],"completion":null},"health":{"engine_state":"Idle"},"plan":{"days":[],"jobs":[],"timeline":[]}}

: heartbeat
```

The desktop uses header-authenticated fetch streaming, retains the last snapshot
on disconnect, and provides Retry. Tokens and private paths must be redacted
before sharing logs.

## P1c reliability changes (partial cycle)

`POST queue` now returns a `preparing` job. Poll queue/SSE until it becomes
queued or failed. Preparation does not download weights. Cancel and pause are
preserved across preparation. A preparing job cannot run before its frame map
and input fingerprint have been stored.

Health `last_error` is null or `{time, job_id, message}`. Running jobs from an
interrupted service are reset at startup, including jobs behind the head.
Operations are persisted in `previews/<id>/state.json`; interrupted operations
are returned as failed with `Interrupted. Try again.`. Trial admission ignores
operating hours but retains the between-segment lease. Trials have a hard
`max(600 seconds, 4 * prediction)` deadline. Whole-file Trial analysis is still
present pending a designer decision; no bounded-start latency claim is made.

Segment children send frame/step/memory heartbeats every two seconds. Queue/SSE
use live frames for processing percent (capped at 99.9% before completion) and
fps. Manifests receive heartbeat updates at most every ten seconds. Dedicated
and shared Windows GPU counters can be unavailable and are then null; RSS is
per PID. Segment stdout/stderr are in `jobs/<id>/logs/seg_NNNNN.log`, trimmed to
the last 1 MiB by the parent. `GET queue/<id>/details` returns `{text}` containing
the manifest and the last 40 segment-log lines.

SSE snapshot exceptions emit `event: error` with plain text and are retried
within the same stream. Heartbeats remain every ten seconds. Snapshot generation,
estimates, thumbnails and input analysis do not hold the shared mutation lock.
The redesigned screens and compare/catalog endpoints are not implemented by
this partial cycle. See `.ai/LAST_REPORT.md` for the remaining acceptance gaps.
