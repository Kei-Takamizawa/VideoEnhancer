# P1d performance harness

Run from `gui` after `npm run build`:

```powershell
npx playwright test tests/perf --config=playwright.perf.config.ts
```

The isolated authenticated fake engine has 1,000 terminal records, ten queued
videos and one running Standard video. It sends progress once per second.
Performance marks use the renderer clock; Event Timing captures input processing
delay/duration. Screen paint uses two animation frames after the actual heading
is visible. CDP TaskDuration divided by thirty seconds measures one-core renderer
CPU. Results are written before budget assertions, including failures.

This fixture measures renderer work only. Real event-snapshot CPU is measured
separately with an isolated real engine home. No owner data or GPU is used by
the renderer harness.

Prepare and measure the real service fixture from the repository root:

```powershell
.venv/Scripts/python.exe gui/tests/perf/prepare_service.py --root C:/private/ve-perf-new --model-home C:/private/verified-model-home
```

The output directory must be new. The model home must already contain verified
C1 and RIFE weights and their adapter sources. No download is attempted. The
helper generates an eight-second synthetic portrait clip, creates 1,000 terminal
records and ten queued records, and runs one actual CUDA Standard job in a
separate controller process. It measures service `process_time` for 31 seconds
after cache warm-up. The authenticated idle HTTP/SSE client is another process,
so its buffered reads do not count as service CPU. Results and controller logs
stay in the private output directory. The controller finishes its synthetic job
before the helper stops it.

The renderer numbers also retain Event Timing interaction duration separately
from input delay (`processingStart - startTime`). A failed budget is still saved
in the JSON report and must be reported as a failure.
