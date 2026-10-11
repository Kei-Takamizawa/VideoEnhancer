"""Registry and lifecycle API coverage without production model downloads."""

import json
import urllib.error

import pytest
from test_model_registry import fake_model as fake_model
from test_service import api as api


def test_registry_add_invalid_hash_verify_and_remove(api, fake_model, monkeypatch):
    engine, _, request = api
    folder, manifest, _ = fake_model
    with request("models", "POST", {"folder": str(folder)}) as response:
        assert json.load(response)["id"] == manifest["id"]
    with request("models") as response:
        assert any(m["id"] == manifest["id"] and m["weights_verified"] for m in json.load(response))
    with request(f"models/{manifest['id']}/verify", "POST", {}) as response:
        operation = json.load(response)
    assert operation["state"] == "waiting"
    engine.cancel_operation(operation["id"])
    assert engine.operations[operation["id"]]["state"] == "cancelled"
    request(f"models/{manifest['id']}", "DELETE").close()
    (folder / "weights.pt").write_bytes(b"wrong weights")
    with pytest.raises(urllib.error.HTTPError) as error:
        request("models", "POST", {"folder": str(folder)})
    assert error.value.code == 400


def test_invalid_advanced_settings_are_rejected(api):
    _, _, request = api
    with pytest.raises(urllib.error.HTTPError) as error:
        request("settings", "PUT", {"advanced": {"clip_length": 15, "clip_overlap": 8}})
    assert error.value.code == 400


def test_trial_starts_outside_hours_and_waiting_cancel(api, video_factory, monkeypatch):
    engine, _, request = api
    request("schedule", "PUT", {"enabled": True, "weekly": []}).close()
    operation = engine.operation(
        "trial",
        {
            "file": str(video_factory(frames=12)),
            "seconds": 3,
            "settings": {"backend": "cpu", "preset": "fast"},
        },
    )
    called = []
    monkeypatch.setattr(engine, "_run_operation", lambda op: called.append(op["id"]))
    engine._auxiliary()
    assert operation["state"] == "done"
    assert called == [operation["id"]]
    operation = engine.operation("verify", {"model_id": "example"})
    request(f"operations/{operation['id']}/cancel", "POST", {}).close()
    assert operation["state"] == "cancelled"


def test_small_standard_output_is_rejected_before_processing(api, video_factory):
    engine, _, request = api
    source = video_factory(frames=12)
    settings = {"preset": "standard", "backend": "cpu", "short_side": "keep"}
    estimate = engine.estimate({"file": str(source), "settings": settings})
    assert any(
        "Output too small" in warning and "256" in warning for warning in estimate["warnings"]
    )
    with pytest.raises(urllib.error.HTTPError) as error:
        request("trial", "POST", {"file": str(source), "seconds": 3, "settings": settings})
    assert error.value.code == 400
    assert not engine.operations
