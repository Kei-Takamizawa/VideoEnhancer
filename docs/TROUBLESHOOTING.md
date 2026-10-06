# Troubleshooting

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
