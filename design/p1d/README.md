# P1d visual design

These seven components are the visual source of truth for P1d: layout, spacing,
colours, copy, states and keyboard behaviour. The app must reimplement the design in
its React and TypeScript renderer using real data. Sample files and model names
are examples. The design runtime is not shipped.

The original 7,153,595-byte export has SHA-256
`f19cd6ed307e71e35ef319f4025b70e6e6a72b9d2e6a87cff165cd3e15d7a642`.
All seven extracted files match the byte lengths and SHA-256 values in the task.
The export, extraction script and runtime are kept outside source control.

## Artboards

| # | Board | Component | Variant | Theme | Size |
|---|---|---|---|---|---|
| 1 | Home | Main | working | dark | 1280x800 |
| 2 | Add videos | AddVideos | default | dark | 1280x800 |
| 3 | History | History | default | dark | 1280x800 |
| 4 | Schedule | Schedule | default | dark | 1280x800 |
| 5 | Models | Models | default | dark | 1280x800 |
| 6 | Compare | Compare | default | dark | 1280x800 |
| 7 | Settings | Settings | default | dark | 1280x800 |
| 8 | Home · light | Main | working | light | 1280x800 |
| 9 | Add videos · light | AddVideos | default | light | 1280x800 |
| 10 | History · light | History | default | light | 1280x800 |
| 11 | Schedule · light | Schedule | default | light | 1280x800 |
| 12 | Models · light | Models | default | light | 1280x800 |
| 13 | Compare · light | Compare | default | light | 1280x800 |
| 14 | Settings · light | Settings | default | light | 1280x800 |
| 15 | Home · 1100 x 700 | Main | working | dark | 1100x700 |
| 16 | Add videos · options open · 1100 x 700 | AddVideos | optionsNoAv1 | dark | 1100x700 |
| 17 | History · 1100 x 700 | History | default | dark | 1100x700 |
| 18 | Schedule · 1100 x 700 | Schedule | default | dark | 1100x700 |
| 19 | Models · 1100 x 700 | Models | default | dark | 1100x700 |
| 20 | Compare · 1100 x 700 | Compare | failed | dark | 1100x700 |
| 21 | Settings · Advanced open · 1100 x 700 | Settings | advanced | dark | 1100x700 |
| 22 | Home · more menu | Main | menu | dark | 1280x800 |
| 23 | Home · waiting for your hours | Main | waiting | dark | 1280x800 |
| 24 | Home · finishing | Main | finishing | dark | 1280x800 |
| 25 | Home · empty queue | Main | empty | dark | 1280x800 |
| 26 | Home · dropping files | Main | drop | dark | 1280x800 |
| 27 | Home · zoom toast | Main | zoom | dark | 1280x800 |
| 28 | Home · preview result | Main | preview | dark | 1280x800 |
| 29 | Home · first close to tray | Main | tray | dark | 1280x800 |
| 30 | Home · long queue scrolls · 1100 x 700 | Main | long | dark | 1100x700 |
| 31 | Home · cancel job | Main | confirmCancel | dark | 1280x800 |
| 32 | Home · remove job | Main | confirmRemove | dark | 1280x800 |
| 33 | Home · job log | Main | log | dark | 1280x800 |
| 34 | Home · action error | Main | actionError | dark | 1280x800 |
| 35 | Home · problem | Main | problem | dark | 1280x800 |
| 36 | Home · connecting | Main | connecting | dark | 1280x800 |
| 37 | Home · reconnecting | Main | reconnecting | dark | 1280x800 |
| 38 | Home · engine unreachable | Main | unreachable | dark | 1280x800 |
| 39 | Home · Smart App Control | Main | sac | dark | 1280x800 |
| 40 | Add videos · more options | AddVideos | options | dark | 1280x800 |
| 41 | Add 1 video · estimating | AddVideos | one | dark | 1280x800 |
| 42 | Add videos · blocking warnings | AddVideos | warnings | dark | 1280x800 |
| 43 | Add videos · adding | AddVideos | busy | dark | 1280x800 |
| 44 | Add videos · partly added | AddVideos | partial | dark | 1280x800 |
| 45 | History · needs attention | History | failed | dark | 1280x800 |
| 46 | History · file not found | History | notFound | dark | 1280x800 |
| 47 | History · select mode | History | select | dark | 1280x800 |
| 48 | History · delete video files | History | deleteFiles | dark | 1280x800 |
| 49 | History · clear history | History | clear | dark | 1280x800 |
| 50 | History · removed, undo | History | toast | dark | 1280x800 |
| 51 | History · empty | History | empty | dark | 1280x800 |
| 52 | History · no match | History | noMatch | dark | 1280x800 |
| 53 | Schedule · add a special day | Schedule | addDay | dark | 1280x800 |
| 54 | Schedule · run now until a time | Schedule | runUntil | dark | 1280x800 |
| 55 | Schedule · working now | Schedule | override | dark | 1280x800 |
| 56 | Schedule · work any time | Schedule | off | dark | 1280x800 |
| 57 | Models · details | Models | details | dark | 1280x800 |
| 58 | Models · licence before download | Models | licence | dark | 1280x800 |
| 59 | Models · remove | Models | remove | dark | 1280x800 |
| 60 | Compare · swipe, landscape | Compare | swipe | dark | 1280x800 |
| 61 | Compare · Fast video | Compare | fast | dark | 1280x800 |

## Derived Home states

`paused`, `preparing`, `overrun` and `previewPause` are defined by Main.dc.html
and are derived states in addition to the exported Home boards.
