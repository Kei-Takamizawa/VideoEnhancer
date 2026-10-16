# Troubleshooting

## Preview and catalog messages

Closing Preview result stops its CPU encoding and removes partial previews;
completed video output is kept. A later preview uses a fresh operation folder.
Compare's Back button returns to the previous screen; use Cancel to stop an
admitted comparison. An expired preview means the five-session/2 GB cache made
room for newer comparisons; compare again.

Change mode and Use this require a job that has not started. Wait for Preparing
to finish first. A model used by queued videos cannot be removed; finish or
remove those queue entries first. Removing a History entry keeps the video.
"Not measured here" is deliberate: no qualifying speed or memory measurement
has been recorded for that model. It is not an estimate copied from a publisher.

If packaging reports EBUSY because the existing package is open, use a fresh
`VE_GUI_PACKAGE_OUT` folder. Do not terminate the owner's running app merely to
build a test package.

## A video's work files are locked

After three consecutive manifest-lock timeouts, VideoEnhancer quarantines that
job and continues other jobs. History shows "Needs attention: this video's work
files are locked by another program. Close that program, then Retry." Close the
program holding the work files and use Retry. Valid completed steps are retained.
The engine records `quarantine.json` beside the job manifest without taking the
blocked manifest lock. Do not delete completed video files to recover the job.

## Windows Smart App Control blocks video startup

### What you may see

VideoEnhancer may report: “PyNvVideoCodec could not start. Windows Smart App Control may have blocked its unsigned NVIDIA video component (VersionCheck.cp312-win_amd64.pyd).” The diagnostic points here. This is a likely cause, not proof: other extension-loading failures can produce a similar import error.

### Technical details and checks

The affected extension is `VersionCheck.cp312-win_amd64.pyd`, part of the PyNvVideoCodec installation. On Windows, an application-control rejection can surface during Python import as `ImportError` or an operating-system image-load error. Windows error 577 (`ERROR_INVALID_IMAGE_HASH`) is one relevant signature-validation error. Check **Windows Security → Protection history** and the Code Integrity operational log around the failure time for corroborating events. The engine currently reports an import failure as a likely Smart App Control issue; it does not yet query these logs, and the message alone does not identify the blocking policy conclusively.

Microsoft's current [Smart App Control FAQ](https://support.microsoft.com/en-us/windows/security/threat-malware-protection/smart-app-control-frequently-asked-questions) says it can be disabled in Windows Security and that recent Windows updates allow enabling it again without reinstalling Windows. Microsoft's [App & browser control documentation](https://support.microsoft.com/en-us/windows/security/windows-security/app-browser-control-in-the-windows-security-app) still describes older installation/reset limitations in its general guidance. Availability depends on the device and Windows build; check the current settings and FAQ for that PC. Windows does not offer an allow-this-one-app bypass. Turning off a security feature is the user's decision.

Options include installing a signed compatible component if NVIDIA provides one, using CPU processing where available, or choosing to disable Smart App Control after reviewing Microsoft's guidance. Do not disable it solely on the basis of this diagnostic.

### FFmpeg fallback investigation

FFmpeg can expose NVIDIA hardware codecs through `*_cuvid` decoders and `*_nvenc` encoders. Such a path could avoid importing PyNvVideoCodec, but VideoEnhancer does not currently use those codecs as a fallback. The existing CPU decode/encode path uses FFmpeg software codecs; the direct CUDA path uses PyNvVideoCodec.

No FFmpeg executable/build was tested for this investigation, so this repository has no verified finding about the signature status of a particular FFmpeg build or whether Smart App Control accepts it. A future investigation should record the exact FFmpeg build/source, inspect its Authenticode signature and each loaded DLL, verify that its build includes the desired CUVID/NVENC codecs, and test it on a machine with Smart App Control enabled. A signed FFmpeg executable alone would not establish that every dependent component is trusted or that the full fallback works.

## Processing remains at zero or stops responding

The segment watchdog allows 300 seconds for the first frame. After frames start,
no new frame for `max(180 seconds, 20 * predicted seconds per frame)` or a total
wall time over `3 * predicted seconds + 300` stops the child tree. One retry uses
a fresh child; another stall fails that job. A child that returns a result but
will not exit is killed after a 15-second grace, retaining its result.

Copy details includes the last 40 lines of the segment log. Memory samples are
logged during processing every 30 seconds and identify the process PID. Missing
Windows GPU counters are recorded as unavailable, not zero. Avoid concluding
that a job is hung from a screenshot alone: compare progress, timestamps and
raw-segment file growth over at least 60 seconds.

Short-lived file sharing errors are retried after 0.2, 0.5, 1, 2 and 4 seconds.
A file-open error asks you to check whether another app owns it or whether a
cloud folder has downloaded it. Controller errors include their traceback in
local logs. Persistent manifest-lock failures still require attention; full
failure quarantine is not implemented in this draft.

After a service restart, unfinished previews show **Interrupted. Try again.**.
Trial rendering ignores your operating hours and waits only for the current
segment. Long-file Trial startup still performs whole-file analysis pending a
range-decoder design decision; the requested 30-second bound is unverified.

## P1d-2 development checks

For cleanup outputs under 256 pixels, choose Use 1080. For AV1 outputs under
the detected minimum (130x66 on the tested RTX 4060 Ti), choose Use HEVC.
Choose a folder for insufficient space, remove HDR inputs, and read the Smart
App Control instructions if Windows blocks FFmpeg. A smaller chosen size is
a nonblocking note; Use Keep preserves the source dimensions.

Estimates remain approximate. Settings identifies the measured or built-in
profile. A driver update retains the newest measurement for the same GPU and
shows the measured/current driver note. With no profile, the uncalibrated range
remains. Speed unknown means the chosen model has no reference: run manual
speed calibration, or add the job with its time left unknown. Calibration's
button shows an approximate duration and offers Cancel while running. See
`.ai/LAST_REPORT.md` for measured accuracy and calibration wall times; these
measurements do not establish performance on other GPUs.

History removal preserves videos. Delete video files is a separate action.
Files on network/removable/FAT/exFAT drives, reparse points and files in use
are kept. Close the player and retry. If recycling is not confirmed, the
hard-link guard restores the original. Keep `deletions.jsonl` and any `.ve-guard-`
file until recovery is resolved; do not remove guards manually.

Kept: the file changed after this job used it means its recorded identity no
longer matches. Recycling off or a file exceeding the readable drive limit
also keeps the file. Unresolved recovery notices show the exact guard path in
History, or Home when no job matches, with Show in folder. A running deletion
owns a cross-process lock; recovery skips its live owner and retries later.
Read-only attributes remain on a successfully recycled file. Restore the exact
file through Windows Recycle Bin if you need it again.

One HDR file does not invalidate estimates for other selected files. Remove
PQ/HLG inputs before adding; API/CLI additions enforce the same warning rules.
Progress can count down between child reports using the last measured speed;
it is an estimate, not an additional completed-frame measurement. Terminal file
presence updates when History opens and in the background every 60 seconds.
Brief Windows sharing violations on preview progress files are retried at the
next poll. If an operation fails, the service stops its remaining child tree
before releasing ownership, so a failed preview cannot silently keep using the
GPU alongside the next operation.
The tray polls status every three seconds. Health replies reuse compact job
metadata rather than copying the full History diagnostics on each poll.

Automatic original deletion is off by default. `Original kept: reason` explains
failed output checks or another unfinished job using the same original.
Compare again requires the original; restore a recycled original with Windows
Recycle Bin before comparing again.

Persistent cancellation cleanup failures reappear in History with their reason.
Clear history reports partial failure, preserving records it could not remove.

## P1e owner-check fixes

Close an open dialog before dropping another video. Add reports problems on the
individual file row: remove an HDR file without discarding other SDR choices.
A correctly tagged BT.2020 PQ/HLG video remains unsupported for processing.
"Checking..." can remain on a large file while packet metadata is read; closing
Add cancels the client's request. A low-space message names required and free GB
on the output volume. Downscaling is included in the byte estimate, which remains
an estimate rather than a guaranteed final codec size.

For an old finished output without recorded identity, deletion requires both its
job-time modification window and matching planned duration. A changed or
unverifiable output is kept. No refusal is bypassed by permanent deletion.
When removing History with file options, retained-file reasons keep those records
visible. Undo restores History records; files remain in the Recycle Bin.

If History cannot play a codec, use Open in your player. The popup streams recorded files and seeks with HTTP byte ranges. If an output
was moved or changed, its warning explains why playback or deletion is refused.

A paused job keeps finished parts and restarts the current part. Its card shows
the estimated work repeated. Schedule hours can be edited with the switch off;
the dimmed hours remain saved until you turn it on.

A model's disabled Uninstall action explains whether it is the default or used
by unfinished work. Full details and supported strength controls are in its
popup. An install failure retains a short card reason and its diagnostic details.

Long-video forecasts include analysis and measured startup costs, locally learned
finalization correction with a safety margin, operating-hours gaps and recent
same-mode timing correction. Initial forecasts are kept in new manifests; old
initial forecasts can only be reconstructed and must be labelled as such.
Corrupted local timing observations are ignored without changing video output.

## Disk-space and codec warnings

Changing HEVC/AV1 or the output folder refreshes the size and space checks without
requesting another processing-time estimate. Output size is an estimate, not a
guaranteed byte count. The preflight allows room for retained segments, their
joined copy and the final temporary file, including a 10% reserve. If output and
engine home are on different volumes, each volume is checked separately.


## Processing stops or a removal takes time

A removal with files runs in the background. Its operation shows each settled
file; the event stream stays connected. A kept file retains its record and
reason. Dismiss hides a message, while logs and the record's warning remain.

If progress stops and later errors, keep the job and use Copy details before
removing its record. Segment logs include the last frame count, elapsed time,
process ID, memory samples and watchdog reason. A fresh-process retry remains
bounded; an error does not establish that the video, GPU driver or hardware is
at fault. Memory samples are observations, not guaranteed peaks.

A missing analysis sidecar is rebuilt for queued work after checking the input
identity. Finished records remain readable. FFmpeg software VP9/AV1 decoder
availability is reported in Settings and when adding the affected formats.
Audio checks use each stream's packets and account for codec priming.

2160p forecasts use measured component and whole-pipeline points. Larger output
is visibly uncalibrated. Old local observations are not silently treated as
measurements of a new built-in profile revision.

## Moving app data and reclaiming working space

If the app data drive is full, open Settings > Storage. It displays the drive's free space and separates models, unfinished working files, and History/logs. Move app data to a new or empty folder while processing is paused. No owner data is moved by development scripts. A nonempty target is refused so unrelated files are not mixed into app data.

If a move fails, the original folder remains selected. Keep the original and inspect the displayed error; do not delete the only good copy. A partial target is retained and must be emptied before retrying. If the new folder is later missing, startup shows **The app data folder was not found** with **Choose...** and **Use the previous folder**. The environment variable `VE_HOME`, when present, overrides the saved selection on the next application launch.

Use **Remove the old folder** only after a successful move. This is permanent deletion. **Clean up** for failed/cancelled jobs removes engine-owned parts and the joined working video, preserving inputs, finished outputs and History. After cleanup Retry processes every part again. The default automatic cleanup period is seven days; it runs when the desktop engine is active.

For development disk growth and the fixed D-drive layout, see [WORKSPACE.md](WORKSPACE.md). Missing historical P1e-2 D-drive evidence was accepted as lost in P1e-2b revision 2; do not attempt to recover or recreate those historical observations.
