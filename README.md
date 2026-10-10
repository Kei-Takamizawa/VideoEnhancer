# VideoEnhancer

VideoEnhancer is a Windows app in development. It can restore compression damage and make motion smoother. It can also resize videos, save progress, resume interrupted jobs, and work within your chosen hours.

Requires an NVIDIA RTX GPU. Your videos stay on your computer.

## Using the app

Add videos, choose Standard or Fast, and follow current work on Home. Find finished videos and retry failed work in History. Set preferred working hours on Schedule, including days off and one-day changes. On Models, review licences and choose defaults for new videos. Compare models on a short part of your video before processing the whole file. You can view pictures together or slide between two, zoom in, and step through matching frames. Preview result shows an already finished step while the rest of the video continues; closing that preview cancels it. Closing the app window keeps processing in the tray; Quit stops safely so you can continue later. The development app needs Windows 11 and an NVIDIA RTX graphics card; see the [app setup guide](docs/GUI.md).

Try a short labeled comparison before processing a whole video. You can also
add your own compatible restoration models and choose them for a job.

For development setup and commands, see the [developer guide](docs/DEVELOPMENT.md). Code is licensed under [MIT](LICENSE); optional AI models have separate licenses.

## Windows Smart App Control

Some Windows 11 PCs have a protection called Smart App Control. It may stop one of the NVIDIA video components from starting because that component is not digitally signed. If VideoEnhancer reports that PyNvVideoCodec could not start and names Smart App Control, this may be the cause. See [troubleshooting](docs/TROUBLESHOOTING.md) for details.

Microsoft currently says you can turn Smart App Control off in Windows Security, and recent Windows updates allow it to be turned on again without reinstalling Windows. Turning off a Windows security feature is your decision. Read [Microsoft's current FAQ](https://support.microsoft.com/en-us/windows/security/threat-malware-protection/smart-app-control-frequently-asked-questions) before changing it.
