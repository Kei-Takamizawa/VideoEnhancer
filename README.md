# VideoEnhancer

English · [日本語](docs/readme/ja.md) · [中文](docs/readme/zh.md) · [हिन्दी](docs/readme/hi.md) · [Español](docs/readme/es.md) · [العربية](docs/readme/ar.md) · [Français](docs/readme/fr.md) · [Bahasa Indonesia](docs/readme/id.md) · [한국어](docs/readme/ko.md) · [Русский](docs/readme/ru.md) · [Português](docs/readme/pt.md)

VideoEnhancer is a Windows app in development. It aims to restore videos damaged by compression and make motion smoother while preserving the original appearance of people, makeup, and color.

The first development version can resize videos, create intermediate frames by blending, save progress, resume interrupted jobs, and work within your chosen hours. AI quality restoration and a graphical interface are planned for later versions.

Requires an NVIDIA RTX GPU. Your videos stay on your computer.

For development setup and commands, see the [developer guide](docs/DEVELOPMENT.md). Code is licensed under [MIT](LICENSE); optional AI models have separate licenses.

## Windows Smart App Control

Some Windows 11 PCs have a protection called Smart App Control. It may stop one of the NVIDIA video components from starting because that component is not digitally signed. If VideoEnhancer reports that PyNvVideoCodec could not start and names Smart App Control, this may be the cause. See [troubleshooting](docs/TROUBLESHOOTING.md) for details.

Microsoft currently says you can turn Smart App Control off in Windows Security, and recent Windows updates allow it to be turned on again without reinstalling Windows. Turning off a Windows security feature is your decision. Read [Microsoft's current FAQ](https://support.microsoft.com/en-us/windows/security/threat-malware-protection/smart-app-control-frequently-asked-questions) before changing it.
