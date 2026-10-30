# Part worker lifecycle

The scheduler owns one isolated processing worker at a time. A reusable worker
belongs to one job and one immutable combination of input, media, scene cuts,
settings and model identities. Models and their weight verification stay in that
worker; decoding, encoders, temporal buffers, memory sampling and per-part
counters start again for each part.

Successful parts can reuse the worker up to 50 parts. Failures, watchdogs, CUDA
OOM (including half-clip or uncapped retries), shared-memory spill, pause and
abort discard it. Changing the job, model or settings also discards it. The
controller's existing watchdog, batch-size and decoder retry ordering remains
unchanged. Preview admission releases the idle worker before auxiliary GPU work;
scheduler waits, job completion and engine shutdown release it too.

On shutdown the parent requests cooperative exit, then kills the process tree
if necessary. The Windows kill-on-close Job Object remains attached throughout
the worker's lifetime. A worker never owns the queue admission policy.

The VE-P1e-3d1 report records the required byte-identity and performance gates;
lifecycle tests alone do not establish those gates.
