"""Local CPU YuNet poster selection. Frames and landmarks live only in memory."""

from __future__ import annotations

import hashlib
import math
import os
import subprocess
import time
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass

import numpy as np

from videoenhancer import proc
from videoenhancer.config import executable

VERSION = 2
MODEL_SHA256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
MODEL_URL = (
    "https://media.githubusercontent.com/media/opencv/opencv_zoo/"
    "48b10fa505aeb51fbd127fc60a5c660040e823b7/"
    "models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
)
MASK_SHA256 = "fcc9e8d5a19b8000e11fbae4e2cb40315c477c32c5dbf533d3a00f84fd258c00"
MASK_URL = (
    "https://huggingface.co/Dao-Dung/face-mask-detector-onnx/resolve/"
    "7f17625a18e809737e4ac44d39fc949994c4c1d1/mask_detector.onnx"
)
MODEL_NAME = "face_detection_yunet_2023mar.onnx"


@dataclass(frozen=True)
class Face:
    quality: float
    unmasked: bool
    good: bool


def candidate_times(duration):
    count = min(300, max(1, math.ceil(duration)))
    return np.linspace(duration * 0.03, duration * 0.97, count).tolist()


def people_count(counts):
    return sorted(counts)[math.ceil(len(counts) * 0.9) - 1] if counts else 0


def choose(frames, duration):
    n = people_count([len(faces) for _, faces in frames])
    if not any(faces for _, faces in frames):
        return None

    def score(item):
        position, faces = item
        good = [face for face in faces if face.good]
        return (
            min(n, len(good)),
            sum(face.unmasked for face in faces),
            sum(face.quality for face in faces),
            -abs(position / duration - min(0.5, max(0.1, position / duration))),
            -abs(position / duration - 0.3),
        )

    position, faces = max(frames, key=score)
    return dict(
        time=position,
        N=n,
        face_count=len(faces),
        unmasked_count=sum(face.unmasked for face in faces),
        version=VERSION,
    )


def classify(session, crop):
    # Bilinear RGB resizing matches the classifier's MobileNetV2 input contract.
    h, w = crop.shape[:2]
    ys = np.clip((np.arange(224) + 0.5) * h / 224 - 0.5, 0, h - 1)
    xs = np.clip((np.arange(224) + 0.5) * w / 224 - 0.5, 0, w - 1)
    y0, x0 = ys.astype(int), xs.astype(int)
    y1, x1 = np.minimum(y0 + 1, h - 1), np.minimum(x0 + 1, w - 1)
    wy, wx = (ys - y0)[:, None, None], (xs - x0)[None, :, None]
    rgb = crop[:, :, ::-1].astype(np.float32)
    resized = (rgb[y0[:, None], x0] * (1 - wx) + rgb[y0[:, None], x1] * wx) * (1 - wy) + (
        rgb[y1[:, None], x0] * (1 - wx) + rgb[y1[:, None], x1] * wx
    ) * wy
    value = (resized / 127.5 - 1).astype(np.float32)[None]
    output = np.asarray(session.run(None, {"input_1": value})[0])[0]
    return bool(output[1] > output[0])


def measure(image, box, landmarks, confidence, mask_session):
    h, w = image.shape[:2]
    x, y, bw, bh = box
    if bh < h * 0.03 or bw < 2 or bh < 2:
        return None
    x0, y0 = max(0, int(x)), max(0, int(y))
    x1, y1 = min(w, int(x + bw)), min(h, int(y + bh))
    if x1 <= x0 or y1 <= y0:
        return None
    crop = image[y0:y1, x0:x1].astype(float).mean(axis=2)
    if min(crop.shape, default=0) < 3:
        return None
    lap = crop[:-2, 1:-1] + crop[2:, 1:-1] + crop[1:-1, :-2] + crop[1:-1, 2:] - 4 * crop[1:-1, 1:-1]
    sharpness = float(lap.var())
    eye_mid = landmarks[:2].mean(axis=0)
    span = max(1, float(np.linalg.norm(landmarks[1] - landmarks[0])))
    symmetry = max(0, 1 - abs(float(landmarks[2, 0] - eye_mid[0])) / span * 2)
    symmetry *= max(0, 1 - abs(float(landmarks[0, 1] - landmarks[1, 1])) / span)
    visible = max(0, x1 - x0) * max(0, y1 - y0) / (bw * bh)
    edge = x <= 1 or y <= 1 or x + bw >= w - 1 or y + bh >= h - 1
    good = not edge and visible >= 0.95 and sharpness >= 5 and symmetry >= 0.25
    quality = bw * bh / (w * h) * symmetry * sharpness * confidence * visible
    return Face(quality * (0.1 if edge else 1), classify(mask_session, image[y0:y1, x0:x1]), good)


class Detector:
    def __init__(self, model, mask_model):
        import onnxruntime as ort  # pyright: ignore[reportMissingImports]

        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(
            str(model), sess_options=options, providers=["CPUExecutionProvider"]
        )

        self.mask_session = ort.InferenceSession(
            str(mask_model), sess_options=options, providers=["CPUExecutionProvider"]
        )

    def detect(self, image, cancelled=lambda: False):
        if cancelled():
            raise InterruptedError("Poster interrupted.")
        height, width = image.shape[:2]
        padded = np.zeros((640, 640, 3), dtype=np.float32)
        padded[:height, :width] = image
        outputs = {
            name: np.asarray(value)
            for name, value in zip(
                [o.name for o in self.session.get_outputs()],
                self.session.run(
                    None, {self.session.get_inputs()[0].name: padded.transpose(2, 0, 1)[None]}
                ),
                strict=True,
            )
        }
        boxes, points, scores = [], [], []
        for stride in (8, 16, 32):
            if cancelled():
                raise InterruptedError("Poster interrupted.")
            confidence = np.sqrt(
                np.clip(outputs[f"cls_{stride}"][0, :, 0], 0, 1)
                * np.clip(outputs[f"obj_{stride}"][0, :, 0], 0, 1)
            )
            indices = np.flatnonzero(confidence >= 0.6)
            grid = np.column_stack(
                (indices % (padded.shape[1] // stride), indices // (padded.shape[1] // stride))
            )
            raw = outputs[f"bbox_{stride}"][0, indices]
            size = np.exp(np.clip(raw[:, 2:], -10, 10)) * stride
            xy = (grid + raw[:, :2]) * stride - size / 2
            boxes.extend(np.column_stack((xy, size)))
            points.extend(
                (outputs[f"kps_{stride}"][0, indices].reshape(-1, 5, 2) + grid[:, None]) * stride
            )
            scores.extend(confidence[indices])
        result = []
        order = np.argsort(scores)[::-1][:5000].tolist()
        while order:
            if cancelled():
                raise InterruptedError("Poster interrupted.")
            index = order.pop(0)
            box = boxes[index]
            face = measure(image, box, points[index], scores[index], self.mask_session)
            if face is not None:
                result.append(face)
            keep = []
            for other in order:
                b = boxes[other]
                intersection = np.maximum(
                    0, np.minimum(box[:2] + box[2:], b[:2] + b[2:]) - np.maximum(box[:2], b[:2])
                ).prod()
                union = box[2:].prod() + b[2:].prod() - intersection
                if intersection / max(1, union) <= 0.3:
                    keep.append(other)
            order = keep
        return result


def load_detector(home, cancelled):
    # Check the optional runtime before any download; offline CPU CI needs neither.
    import onnxruntime  # noqa: F401  # pyright: ignore[reportMissingImports]

    for folder in (home / "models", home / "models" / "face"):
        if folder.is_symlink() or folder.is_junction():
            raise ValueError("Invalid detector folder.")
    folder = home / "models" / "face"
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, url, checksum, limit in (
        (MODEL_NAME, MODEL_URL, MODEL_SHA256, 300_000),
        ("mask_detector.onnx", MASK_URL, MASK_SHA256, 10_000_000),
    ):
        if cancelled():
            raise InterruptedError("Poster interrupted.")
        model = folder / name
        if model.is_symlink() or model.is_junction():
            raise ValueError("Invalid detector model.")
        if (
            not model.exists()
            or model.stat().st_size > limit
            or hashlib.sha256(model.read_bytes()).hexdigest() != checksum
        ):
            data = bytearray()
            with urllib.request.urlopen(url, timeout=5) as response:
                while len(data) <= limit:
                    if cancelled():
                        raise InterruptedError("Poster interrupted.")
                    chunk = response.read1(min(65536, limit + 1 - len(data)))
                    if not chunk:
                        break
                    data.extend(chunk)
            if cancelled():
                raise InterruptedError("Poster interrupted.")
            if len(data) > limit or hashlib.sha256(data).hexdigest() != checksum:
                raise ValueError("Invalid detector checksum.")
            model.write_bytes(data)
        paths.append(model)
    return Detector(*paths)


@contextmanager
def background_thread():
    # Thread-scoped priority leaves the service and its GPU workers unchanged.
    if os.name == "nt":
        import ctypes

        kernel = ctypes.windll.kernel32
        handle = kernel.GetCurrentThread()
        changed = kernel.SetThreadPriority(handle, 0x00010000)
        try:
            yield
        finally:
            if changed:
                kernel.SetThreadPriority(handle, 0x00020000)
    else:
        yield


def decode(path, position, width, height, cancelled, deadline):
    command = [
        executable("ffmpeg"),
        "-nostdin",
        "-v",
        "error",
        "-threads",
        "1",
        "-filter_threads",
        "1",
        "-ss",
        str(position),
        "-protocol_whitelist",
        "file,pipe",
        "-i",
        str(path),
        "-an",
        "-frames:v",
        "1",
        "-vf",
        f"scale={width}:{height}",
        "-pix_fmt",
        "bgr24",
        "-f",
        "rawvideo",
        "pipe:1",
    ]
    with proc.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
        try:
            while True:
                if cancelled():
                    raise InterruptedError("Poster interrupted.")
                if time.monotonic() > deadline:
                    raise TimeoutError("Face poster time budget exceeded.")
                try:
                    data, _ = process.communicate(timeout=0.1)
                    break
                except subprocess.TimeoutExpired:
                    pass
            if process.returncode or len(data) != width * height * 3:
                raise ValueError("Cannot decode poster sample.")
            return np.frombuffer(data, dtype=np.uint8).reshape(height, width, 3)
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()


def select(path, metadata, home, cancelled):
    started = time.monotonic()

    def check():
        if cancelled():
            raise InterruptedError("Poster interrupted.")
        if time.monotonic() - started > 60:
            raise TimeoutError("Face poster time budget exceeded.")
        return False

    with background_thread():
        check()
        detector = load_detector(home, check)
        width = max(2, round(min(640, 640 * metadata["width"] / metadata["height"]) / 2) * 2)
        height = min(640, max(2, round(width * metadata["height"] / metadata["width"] / 2) * 2))
        frames = []
        for position in candidate_times(metadata["duration"]):
            check()
            image = decode(path, position, width, height, check, started + 60)
            frames.append((position, detector.detect(image, check)))
            check()
        result = choose(frames, metadata["duration"])
    return result, time.monotonic() - started
