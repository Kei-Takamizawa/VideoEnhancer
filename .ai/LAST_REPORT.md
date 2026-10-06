# VideoEnhancer P0 実装・検証レポート

## 概要（R1–R9）

- R1: Windows/NVIDIA向けPythonプロジェクト、CLI、依存ロック、CIを追加。`p0-test` はGPUリサイズ＋フレーム平均による2倍化で、AIモデルは出力経路に組み込んでいない。
- R2: FFprobe解析、CFR正規化、音声メタデータ保持を実装。実サンプル5本のフレーム数は設計値（532、326、375、561、911）と一致。2997/100の入力は規定の30000/1001に正規化。
- R3: NVDEC→GPUテンソル処理→NVENC経路とCPUテスト用経路、色変換、Main10出力を実装。
- R4: フレーム境界セグメント、原音声の最終mux、ジョブ保存・再開・破損セグメント検証を実装。HE-AACのencoder primingをprobeし、音声オフセットと、primingを考慮した提示尺を検証する。出力muxを原音声トラック終端まで継続し、音声をセグメント処理せずストリームコピー。
- R5: 入力サイズ・ハッシュと空き容量を確認してジョブ作成。
- R6: 週次時間帯、日付例外、手動オーバーライド、タイムゾーン対応スケジューラーを実装。
- R7: GPU計測プロファイルと区間コストから所要時間を予測。
- R8: キュー順の複数ジョブ日程表を実装。
- R9: I/O、テンソル段階、E2E、候補AIモデルの計測と第三者モデル一覧を実装。

## 環境

- Windows 11 Home build 26300、NVIDIA GeForce RTX 4060 Ti 8 GB、driver 617.14。
- Python 3.12.14、PyTorch 2.14.1+cu130、CUDA 13.0、PyNvVideoCodec 2.2.3、FFmpeg 9.0.2。
- GPU利用可能。Smart App Controlが有効な間はWindowsがPyNvVideoCodecのunsigned `VersionCheck.cp312-win_amd64.pyd` を遮断し、ネイティブデコーダーのimportを妨げていた。ユーザーがSmart App Controlを無効化した後、import成功、`CUDA True`、RTX 4060 Ti検出、GPUテスト13件成功を確認。

## 受け入れ基準（A–L）

| ID | 結果 | 検証・数値 |
|---|---|---|
| A Setup | PASS | `uv lock --check`、Ruff、Pyright、CLI。GitHub Actions run 16 はWindows/Ubuntu両方の全job成功。|
| B Probe | PASS | 合成テストとVideosの5本。各入力720×1280、フレーム数532/326/375/561/911。2997/100は30000/1001へ正規化。|
| C Geometry/timing | PASS | CPU全体テストとGPUテスト。5本すべて1080×1920、HEVC Main10、出力2Nフレーム。音声の開始オフセットを保持し、HE-AACのpriming分以外の尺差20 ms以内、デコードPCMは元と完全一致。GPU出力fpsは60000/1001または60。|
| D Color | PASS | GPU lossless往復テスト（8-bit/10-bit）。YUV誤差0、PSNRは無限大（完全一致）。|
| E Resume | PASS | 3分合成素材でCPU 3回・GPU 3回の強制終了後に再開。各10,800出力フレームで基準との比較一致、残存一時ファイル0。|
| F Scheduler | PASS | DST、日跨ぎ、例外、15分制約、実行時間外の停止・再開をテスト。|
| G Planner | PASS | 複数ジョブ・日程、順序変更、スケジュール変更のテスト。|
| H Estimate | PASS | 初期推定3,275.94秒に対し処理実績2,763.30秒（誤差+18.55%）。10%地点の再推定2,781.53秒（誤差+0.66%）。許容±30%/±15%以内。|
| I Soak | FAIL（GPUメモリ条件） | 2時間合成入力215,784フレーム、121/121区間成功、停止・再開2回成功、出力431,568フレーム/7,199.993秒、wall 4,821.18秒、GPU engine 2,525.03秒（85.46入力fps）、解析224.46秒。クラッシュ/一時ファイル0。RSSピーク1.832GB、比較窓のRSS増加8.05MB（上限200MB以内）。全デバイスNVMLは基準からの増加234.87MBで上限100MBを超過。WDDM下でNVMLに当該プロセス別メモリがなく他プロセスも動作していたため、アプリ起因かを分離できず、基準は未達として記録。Torch allocatorの先頭/末尾30区間ピーク差は+37.75MBだが、NVDEC/NVENC等ネイティブメモリを含まないので代替合格にはしない。|
| J Bench | PASS | Part A完了。必須のBasicVSR++、Real-ESRGAN、RIFE、CodeFormer、SCRFDを実測。KEEPとBiSeNetは権利確認済みの互換アダプターがないため重みを取得せずスキップ。|
| K Disk check | PASS | 注入した空き容量値で`ve add`が明確なエラーを返すテスト。|
| L Hygiene | PASS | `git status`対象に動画、モデル重み、出力動画を含めず。LICENSE未変更。|

CPUテスト最終結果: `pytest -m "not gpu and not soak"` → 96 passed, 3 skipped, 13 deselected (13.48 s、最終GitHub Linux run 17.73 s)。GPUスイート: `pytest -m gpu` → 13 passed, 99 deselected (8.81 s)。Lint/format/type: Ruff全件成功、61ファイル整形済み、Pyright 0 errors/warnings/informations。`uv lock --check`成功。GitHub Actions run 16はWindows/Ubuntu両job成功。

Soak判定は設計書の条件を適用し、デバイス全体NVMLの+234.87MBが100MB上限を超えたためFAILとした。WDDMではNVMLのプロセス別メモリ値が取得できず、システム全体の値を当該アプリに帰属できない。Torch allocatorは先頭/末尾30区間の最大値が551.55/589.30MB（+37.75MB）だが、NVDEC/NVENC等のネイティブ割当を含まないため、NVML条件の合格代用とはしていない。

GPU有効化の原因: Smart App ControlがPyNvVideoCodecのunsigned `VersionCheck.cp312-win_amd64.pyd`を遮断していた。ユーザーが同機能を無効化後、PyNvVideoCodec import、CUDA利用可能、RTX 4060 Ti検出を確認した。

## 実行コマンド

- 環境/静的検査: `uv sync --locked`; `uv lock --check`; `ruff check .`; `ruff format --check`; `pyright src`; `pytest -m "not gpu and not soak"`。
- GPU: `pytest -m gpu`; 各サンプルへ `ve enhance <input> --backend cuda`。
- Soak: `python scripts/soak.py --input <2h synthetic> --output <destination>`。実測ジョブID `e91d16763b0d4109890d5c7336123422`、結果JSON `.ve-home/reports/soak_report.json`。
- ベンチ: `ve bench --calibrate`; `ve bench --models all`; `ve bench --models rife`（RIFE再計測）。

## 実動画5本でのGPU出力

すべてRTX 4060 Ti、NVDEC/NVENC、HEVC Main10/P010、P7/high_quality、constqp 18、1080×1920。各出力は2倍フレーム数。検出カット数はnoachan1が9。

| 入力 | 入力フレーム | 出力fps | NVENC出力ビットレート | 実処理秒 | 全体秒 | PyTorch予約VRAMピーク | NVML増分ピーク |
|---|---:|---:|---:|---:|---:|---:|---:|
| HaYeon1.MP4 | 532 | 60 | 24,903,849 bps | 7.84 | 未記録 | 552 MB | 未計測 |
| HaYeon2.MP4 | 326 | 60000/1001 | 17,057,334 bps | 3.69 | 8.63 | 501 MB | 900 MB |
| JooBin+Sullin1.MP4 | 375 | 60 | 18,601,547 bps | 6.00 | 未記録 | 501 MB | 未計測 |
| Kotone+Lynn1.MP4 | 561 | 60000/1001 | 32,706,411 bps | 6.23 | 11.44 | 539 MB | 933 MB |
| noachan1.MP4 | 911 | 60000/1001 | 26,609,041 bps | 9.94 | 15.56 | 539 MB | 938 MB |

既知事項・リスク: Soakのデバイス全体NVML使用量増加が条件を超え、プロセス帰属もできないためGPUメモリ漏れ条件は未達。修正にはWDDM対応のプロセス別GPUメモリ採取を次回Soakで記録して再計測する必要がある。Real-ESRGAN batch 16の7.64GBピークは8GB GPUで余裕が小さく、後続統合時にbatch/tile制御が必要。GPU SoakがFAILのためPRはdraftのまま。

NVML増分は当該プロセスのNVML基準値との差で、PyTorch予約量とは別指標。入力映像に対して音声トラックが0.105–0.146秒長いHE-AAC素材を含む。出力は音声を再エンコードせずコピーし、AAC primingを含む入力のデコードPCMサンプル列を保つ。FFprobeのトラック尺はAAC priming相当（最大約115 ms）短く表示される場合がある。動画トラックは規定のフレーム数・FPSで保持する。

## ベンチマーク

`ve bench --models all` のPart Aと、修正後のRIFE単独50回計測を統合。詳細なURL、SHA-256、測定形状・batch/tile、ライセンス、スキップ理由は以下の同梱レポートを参照。

# VideoEnhancer benchmark report

Created: 2026-10-06T08:48:41Z

GPU: NVIDIA GeForce RTX 4060 Ti; driver: 617.14; VRAM: 8585216000 bytes.
OS: Windows 11 (AMD64); Python: 3.12.14; PyTorch: 2.14.1+cu130; CUDA: 13.0; TensorRT: None.

## Part A: I/O and placeholder stages

Timings marked skipped were not measured. Tensor-only timings exclude video I/O.

| Component | Status | Result |
|---|---|---|
| NVDEC: h264_720x1280 | measured | 1849.99 fps |
| NVDEC: hevc_1080x1920 | measured | 1173.94 fps |
| NVENC: hevc_main10 | measured | 190.77 fps |
| NVENC: h264 | measured | 431.84 fps |
| NVENC: av1 | measured | 375.95 fps |
| Tensor stages: resize | measured | median 0.832 ms; p90 0.838 ms |
| Tensor stages: color_nv12_to_rgb | measured | median 0.477 ms; p90 0.505 ms |
| Tensor stages: color_rgb_to_nv12 | measured | median 0.484 ms; p90 0.517 ms |
| Tensor stages: color_rgb_to_nv12_1080p | measured | median 0.774 ms; p90 0.789 ms |
| Tensor stages: resize_stage | measured | median 1.271 ms; p90 1.579 ms |
| Tensor stages: blend2x | measured | median 0.744 ms; p90 0.788 ms |
| Tensor stages: p0_test_end_to_end | measured | 2058.57 fps |

## Part B: candidate models

No weights are downloaded unless a trusted expected SHA-256 is configured.

| Model | License | Source / weights | SHA-256 | Result | Peak VRAM | Input / batch / tile | Precision / loader |
|---|---|---|---|---|---|---|---|
| BasicVSR++ NTIRE 2021 compressed-video enhancement | Apache-2.0 | Source: https://codeload.github.com/open-mmlab/mmagic/zip/0a560bba9b79ebe78574e1d4cbbdd0e798e63568<br>Weights: https://download.openmmlab.com/mmediting/restorers/basicvsr_plusplus/basicvsr_plusplus_c128n25_ntire_decompress_track3_20210304-6daf4a40.pth | actual: 6daf4a405b0ff7221e3ac39b0a5c788468ae17661c577a3353b9fd477d0c983a<br>source: faf15899d1a558a80a2b835e9efc1dff517d27070b06b3f265258ae0adceb9b1 | measured; median 4819.271 ms; p90 4836.055 ms | 1033895936 bytes | input_shape: [1, 15, 3, 1280, 720]; inference_resolution: "720x1280 (width x height)"; batch_size: 1; clip_frames: 15; tile: [1280, 720] | precision: float16; adapter: torchvision.ops.deform_conv2d; pinned external MMagic source |
| CelebAMask-HQ face parsing (BiSeNet) | Dataset/model terms must be confirmed for the selected checkpoint | Source: https://github.com/zllrunning/face-parsing.PyTorch<br>Weights: https://github.com/zllrunning/face-parsing.PyTorch | not published | skipped; No compatible, rights-reviewed benchmark adapter is implemented for this model; no checkpoint download or inference was attempted. | not reported | not recorded | not recorded |
| CodeFormer | NTU S-Lab License 1.0 (non-commercial) | Source: https://github.com/sczhou/CodeFormer<br>Weights: https://github.com/sczhou/CodeFormer/releases/download/v0.1.0/codeformer.pth | actual: 1009e537e0c2a07d4cabce6355f53cb66767cd4b4297ec7a4a64ca4b8a5684b7<br>source: a67033e34186f05599caed7ae24abea1b18335ca21591741f1d66f1ccc592eae | measured; median 459.765 ms; p90 460.362 ms; batch 1: measured, median 55.575 ms / batch 4: measured, median 229.047 ms / batch 8: measured, median 459.765 ms | 4815060992 bytes | input_shape: [8, 3, 512, 512]; batch_size: 8; largest_tested_working_batch: 8 | precision: float16; adapter: External original network; FP16 embedding lookup replaces its float32 one-hot multiply. |
| KEEP | NTU S-Lab License 1.0 (non-commercial) | Source: https://github.com/jnjaby/KEEP<br>Weights: https://github.com/jnjaby/KEEP/releases | not published | skipped; No compatible, rights-reviewed benchmark adapter is implemented for this model; no checkpoint download or inference was attempted. | not reported | not recorded | not recorded |
| Real-ESRGAN realesr-general-x4v3 | BSD-3-Clause | Source: https://github.com/xinntao/Real-ESRGAN<br>Weights: https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth | expected: 8dc7edb9ac80ccdc30c3a5dca6616509367f05fbc184ad95b731f05bece96292<br>actual: 8dc7edb9ac80ccdc30c3a5dca6616509367f05fbc184ad95b731f05bece96292 | measured; median 3368.433 ms; p90 3381.120 ms | 7640747520 bytes | input_shape: [16, 3, 1280, 720]; output_shape: [16, 3, 5120, 2880]; batch_size: 16; tile: "whole frame" | precision: float16; loader: spandrel ModelLoader |
| Practical-RIFE 4.25 | MIT | Source: https://github.com/hzwer/Practical-RIFE<br>Weights: https://drive.google.com/file/d/1ZKjcbmt1hypiFprJPIKW0Tt0lr_2i7bg/view | expected: 6615790efd627772917205db291f51cd392528a157ecbb2ecaeec3bff8eb6de2<br>actual: 6615790efd627772917205db291f51cd392528a157ecbb2ecaeec3bff8eb6de2<br>source: 88a04ad797a8e831110b771fdcd56b6be4ad66a0ad99c8e82be2a92834bdebc2<br>archive: e63d481b7ae5d4a4e6ad7ac5b410ff78f3bf7be3b51b2e38ca8152747abde5b4 | measured; median 46.249 ms; p90 46.477 ms | 1155530752 bytes | input_shape: [1, 6, 1920, 1088] (8 px horizontal padding); source_resolution: 1080x1920; batch_size: 1; tile: "whole frame" | precision: float16; backend: Practical-RIFE IFNet; external original source |
| SCRFD 500m buffalo_sc detector | InsightFace public model weights: non-commercial research only | Source: https://github.com/deepinsight/insightface<br>Weights: https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_sc.zip | actual: 5e4447f50245bbd7966bd6c0fa52938c61474a04ec7def48753668a9d8b4ea3a<br>archive: 57d31b56b6ffa911c8a73cfc1707c73cab76efe7f13b675a05223bf42de47c72 | measured; median 4.573 ms; p90 4.776 ms | 1333972992 bytes | input_shape: [1280, 720, 3]; input_source_resolution: "720x1280"; inference_resolution: "640x640 letterboxed"; batch_size: 1; tile: "whole frame" | precision: float32; backend: ONNX Runtime with CUDAExecutionProvider and CPUExecutionProvider; provider_placement_note: CUDAExecutionProvider is requested and CPUExecutionProvider is enabled as fallback; per-node placement was not profiled, so some graph nodes may run on CPU. |

Peak NVML VRAM: 8561672192 bytes; peak torch VRAM: 7640747520 bytes; peak RSS: 2740043776 bytes.

## 既知事項・再現手順

- Real-ESRGAN batch 16のピークTorch VRAMは7.64 GBで、8 GBカードのVRAMを大きく消費する。P0処理経路の実測ピークは5サンプルで約0.50–0.55 GB Torch予約、約0.90–1.00 GB NVML増分。
- SCRFDはCUDAとCPU fallback providerを要求したが、ONNX graphのnode配置をprofileしていないため、一部nodeがCPUで実行された可能性がある。
- RIFEは内部encoderのstride条件に合わせて1920×1088でベンチし、中央値46.249 ms、p90 46.477 ms、Torch予約1.156 GB。実動画はP0のblend placeholderのままでRIFE推論を適用していない。
- `ve bench --models all --output-dir <dir>`。RIFEだけ再計測する場合は`ve bench --models rife --output-dir <dir>`。
- `VE_SAMPLES_DIR=Videos`を設定し、各サンプルに`ve enhance <input> --backend cuda`を実行。生成動画は作業フォルダへ追加しない。
- GPUテスト: `pytest -m gpu`。2時間耐久: `python scripts/soak.py --input <2h synthetic> --output <destination>`。校正プロファイルは同じ`VE_HOME`に置く。
