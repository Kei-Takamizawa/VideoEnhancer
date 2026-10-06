# VideoEnhancer

VideoEnhancer is a Windows app in development. From the command line, it can restore compression damage and make motion smoother. It can also resize videos, save progress, resume interrupted jobs, and work within your chosen hours. A graphical interface is planned.

Requires an NVIDIA RTX GPU. Your videos stay on your computer.

For development setup and commands, see the [developer guide](docs/DEVELOPMENT.md). Code is licensed under [MIT](LICENSE); optional AI models have separate licenses.

## Windows Smart App Control

Some Windows 11 PCs have a protection called Smart App Control. It may stop one of the NVIDIA video components from starting because that component is not digitally signed. If VideoEnhancer reports that PyNvVideoCodec could not start and names Smart App Control, this may be the cause. See [troubleshooting](docs/TROUBLESHOOTING.md) for details.

Microsoft currently says you can turn Smart App Control off in Windows Security, and recent Windows updates allow it to be turned on again without reinstalling Windows. Turning off a Windows security feature is your decision. Read [Microsoft's current FAQ](https://support.microsoft.com/en-us/windows/security/threat-malware-protection/smart-app-control-frequently-asked-questions) before changing it.
