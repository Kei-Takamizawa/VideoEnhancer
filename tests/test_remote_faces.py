"""Face-aware poster policy, independent of optional inference or network."""

import pytest

from videoenhancer.remote import faces


def face(*, quality=1.0, unmasked=True, good=True):
    return faces.Face(quality, unmasked, good)


def test_all_visible_beats_large_single():
    frames = [(1.0, [face(quality=100)]), (2.0, [face(), face()])]
    assert faces.choose(frames, 10)["time"] == 2


def test_unmasked_preferred_and_masked_accepted():
    masked = face(quality=100, unmasked=False)
    assert faces.choose([(1, [masked]), (2, [face()])], 10)["time"] == 2
    result = faces.choose([(1, [masked]), (2, [face(unmasked=False)])], 10)
    assert result["time"] == 1
    assert result["unmasked_count"] == 0


def test_unmasked_preference_when_both_faces_are_soft():
    result = faces.choose(
        [
            (1, [face(quality=100, unmasked=False, good=False)]),
            (2, [face(quality=1, unmasked=True, good=False)]),
        ],
        10,
    )
    assert result["time"] == 2


def test_edge_cut_does_not_beat_good_face():
    result = faces.choose([(1, [face(quality=100, good=False)]), (2, [face()])], 10)
    assert result["time"] == 2


def test_no_faces_and_percentile_and_tie():
    assert faces.choose([(1, []), (2, [])], 10) is None
    assert faces.people_count([0] * 5 + [2] * 4 + [10]) == 2
    assert faces.people_count([]) == 0
    assert faces.choose([(i, [] if i else [face()]) for i in range(20)], 20)["N"] == 0
    assert faces.choose([(9, [face()]), (3, [face()])], 10)["time"] == 3


def test_sampling():
    positions = faces.candidate_times(600)
    assert len(positions) == 300
    assert positions[0] == pytest.approx(18)
    assert positions[-1] == pytest.approx(582)
    assert len(faces.candidate_times(10)) == 10


def test_version_and_retry():
    from videoenhancer.remote.thumbnails import current_images

    assert not current_images({"signature": "a"}, "a")
    assert not current_images({"signature": "a", "version": faces.VERSION - 1}, "a")
    assert not current_images(
        {"signature": "a", "version": faces.VERSION, "face_ready": False}, "a"
    )
    assert current_images({"signature": "a", "version": faces.VERSION, "face_ready": True}, "a")


def test_classifier_input_and_labels():
    import numpy as np

    class Session:
        def run(self, outputs, inputs):
            value = inputs["input_1"]
            assert value.shape == (1, 224, 224, 3)
            assert value.dtype == np.float32
            assert value[0, 0, 0].tolist() == pytest.approx([1, -1, -1])
            return [np.array([[0.1, 0.9]])]

    image = np.zeros((10, 10, 3), dtype=np.uint8)
    image[:, :, 2] = 255
    assert faces.classify(Session(), image)


def test_detector_letterboxes_to_fixed_model_input():
    import numpy as np

    class Input:
        name = "input"

    class Session:
        def get_inputs(self):
            return [Input()]

        def get_outputs(self):
            return []

        def run(self, outputs, inputs):
            assert inputs["input"].shape == (1, 3, 640, 640)
            raise RuntimeError("shape verified")

    detector = object.__new__(faces.Detector)
    detector.session = Session()
    with pytest.raises(RuntimeError, match="shape verified"):
        detector.detect(np.zeros((360, 640, 3), np.uint8))


def test_select_fake_detector(tmp_path, monkeypatch):
    import numpy as np

    calls = iter([[face(quality=100)], [face(), face()], []])

    class Detector:
        def detect(self, image, cancelled):
            return next(calls)

    monkeypatch.setattr(faces, "load_detector", lambda home, cancelled: Detector())
    monkeypatch.setattr(faces, "decode", lambda *args: np.zeros((360, 640, 3), np.uint8))
    result, _ = faces.select(
        None, dict(duration=3, width=1920, height=1080), tmp_path, lambda: False
    )
    assert result["face_count"] == result["N"] == 2


def test_cancel_does_not_decode(tmp_path, monkeypatch):
    monkeypatch.setattr(faces, "load_detector", lambda *args: object())
    monkeypatch.setattr(faces, "decode", lambda *args: pytest.fail("decoded while GPU busy"))
    with pytest.raises(InterruptedError):
        faces.select(None, dict(duration=3, width=1920, height=1080), tmp_path, lambda: True)


def test_download_checksum_and_offline(tmp_path, monkeypatch):
    pytest.importorskip("onnxruntime")
    import io

    monkeypatch.setattr(faces.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(b"invalid"))
    with pytest.raises(ValueError, match="checksum"):
        faces.load_detector(tmp_path, lambda: False)
    assert not list(tmp_path.rglob("*.onnx"))


def test_download_checks_cancel_between_chunks(tmp_path, monkeypatch):
    pytest.importorskip("onnxruntime")
    import io

    class Response(io.BytesIO):
        calls = 0

        def read(self, *args):
            pytest.fail("Download must yield between available chunks")

        def read1(self, *args):
            self.calls += 1
            return b"chunk"

    response = Response()
    monkeypatch.setattr(faces.urllib.request, "urlopen", lambda *a, **k: response)
    with pytest.raises(InterruptedError):
        faces.load_detector(tmp_path, lambda: response.calls > 0)
    assert response.calls == 1
    assert not list(tmp_path.rglob("*.onnx"))


def test_detector_checks_cancel_before_inference():
    import numpy as np

    detector = object.__new__(faces.Detector)
    with pytest.raises(InterruptedError):
        detector.detect(np.zeros((360, 640, 3), np.uint8), lambda: True)


def test_deadline_includes_loading(tmp_path, monkeypatch):
    clock = iter([0, 61])
    monkeypatch.setattr(faces.time, "monotonic", lambda: next(clock))

    def load(home, cancelled):
        cancelled()
        return object()

    monkeypatch.setattr(faces, "load_detector", load)
    monkeypatch.setattr(faces, "decode", lambda *args: pytest.fail("deadline ignored"))
    with pytest.raises(TimeoutError):
        faces.select(None, dict(duration=3, width=1920, height=1080), tmp_path, lambda: False)


@pytest.mark.parametrize("ready", [True, False])
def test_watcher_regenerates_old_version_once_or_retries_later(tmp_path, monkeypatch, ready):
    import json
    import threading

    from videoenhancer.remote.library import Library
    from videoenhancer.remote.thumbnails import Thumbnails

    library = Library(tmp_path / "home", tmp_path / "library")
    library.folder.mkdir()
    path = library.folder / "clip.mp4"
    path.write_bytes(b"synthetic")
    images = Thumbnails(library)
    folder = images._folder(library._identifier(path))
    folder.mkdir()
    old = {"signature": images.signature(path.stat()), "version": 1}
    (folder / "storyboard.json").write_text(json.dumps(old))
    calls = []
    event = threading.Event()

    def generate(identifier):
        calls.append(identifier)
        index = {**old, "version": faces.VERSION, "face_ready": ready}
        (folder / "storyboard.json").write_text(json.dumps(index))
        event.set()
        return index

    monkeypatch.setattr(images, "generate", generate)
    images.thread.start()
    try:
        assert event.wait(3)
        assert not images.stop.wait(1.2)
        assert len(calls) == 1
    finally:
        images.close()


@pytest.mark.parametrize("kind", ["one", "two", "masked", "removes"])
def test_real_model_clips(tmp_path, ffmpeg_run, monkeypatch, kind):
    """Optional local public-domain NASA photo; no network in CI or test runs."""
    import json
    import os
    import shutil
    from pathlib import Path

    pytest.importorskip("onnxruntime")
    source = Path(os.environ.get("VE_FACE_TEST_ASSETS", ""))
    if not all(
        (source / name).is_file()
        for name in (faces.MODEL_NAME, "mask_detector.onnx", "astronaut.png")
    ):
        pytest.skip("Optional pinned face models and public-domain NASA image absent")
    from videoenhancer.remote.library import Library
    from videoenhancer.remote.thumbnails import Thumbnails

    library = Library(tmp_path / "home", tmp_path / "library")
    library.folder.mkdir()
    models = library.home / "models" / "face"
    models.mkdir(parents=True)
    for name in (faces.MODEL_NAME, "mask_detector.onnx"):
        shutil.copyfile(source / name, models / name)
    path = library.folder / f"{kind}.mp4"
    observations = []
    detect = faces.Detector.detect

    def observe(detector, image, cancelled):
        detected = detect(detector, image, cancelled)
        observations.append(detected)
        return detected

    monkeypatch.setattr(faces.Detector, "detect", observe)
    filters = "null"
    if kind in ("masked", "removes"):
        filters = "drawbox=x=180:y=118:w=85:h=45:color=lightblue:t=fill"
        if kind == "removes":
            filters += ":enable='lt(t,2)'"
    if kind == "two":
        filters = "split[a][b];[a][b]hstack"
    ffmpeg_run(
        "-loop",
        "1",
        "-i",
        str(source / "astronaut.png"),
        "-t",
        "4",
        "-r",
        "10",
        "-filter_complex",
        filters,
        "-c:v",
        "libx264",
        "-threads",
        "2",
        "-pix_fmt",
        "yuv420p",
        str(path),
    )
    images = Thumbnails(library)
    identifier = library._identifier(path)
    index = images.generate(identifier)
    result = json.loads((images._folder(identifier) / "poster.json").read_text())
    assert index["face_ready"]
    assert result["N"] == result["face_count"] == (2 if kind == "two" else 1)
    assert result["unmasked_count"] == (0 if kind == "masked" else result["face_count"])
    if kind == "removes":
        assert result["time"] >= 2
    assert len(observations) == 4
    correct = total = 0
    for i, detected in enumerate(observations):
        assert len(detected) == (2 if kind == "two" else 1)
        expected = kind not in ("masked", "removes") or (kind == "removes" and i >= 2)
        for face in detected:
            total += 1
            correct += face.unmasked == expected
    assert correct == total
    assert not list(images._folder(identifier).glob("*.raw"))
    print(kind, result, "mask accuracy", correct, "/", total)
