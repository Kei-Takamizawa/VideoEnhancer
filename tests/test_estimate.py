import pytest

from videoenhancer.estimate import estimate_job, predict_segment, update_correction

MEDIA = {"width": 720, "height": 1280, "average_fps": "30000/1001", "cfr_fps": "30000/1001"}
SETTINGS = {"preset": "p0-test", "short_side": 1080, "fps": "2x", "backend": "cuda"}


def manifest():
    return {
        "media": MEDIA,
        "settings": SETTINGS,
        "segments": [
            {"start": 0, "end": 100, "state": "done"},
            {"start": 100, "end": 200, "state": "pending"},
            {"start": 200, "end": 300, "state": "running"},
        ],
    }


def test_initial_range_pending_sum_and_uncalibrated_flag():
    result = estimate_job(manifest())
    assert result.seconds == pytest.approx(2 * predict_segment(MEDIA, SETTINGS, 100))
    assert result.low == result.seconds * 0.75
    assert result.high == result.seconds * 1.25
    assert not result.calibrated
    assert result.to_dict()["seconds"] == result.seconds


def test_profile_uses_component_geometry_and_overhead():
    profile = {
        "components": {
            "decode": {"seconds_per_pixel_frame": 1e-7},
            "color": 0,
            "encode": 0,
            "resize": 0,
            "blend2x": 0,
        },
        "segment_overhead_seconds": 4,
    }
    assert predict_segment(MEDIA, SETTINGS, 10, profile) == pytest.approx(
        720 * 1280 * 10 * 1e-7 + 4
    )
    assert estimate_job(manifest(), profile).calibrated


def test_ema_applies_actual_corrected_prediction_to_remaining():
    job = manifest()
    original = estimate_job(job).seconds
    update_correction(job, predicted=10, actual=20)
    assert job["correction_factor"] == pytest.approx(1.3)
    assert estimate_job(job).seconds == pytest.approx(original * 1.3)
    update_correction(job, predicted=13, actual=20)
    assert job["correction_factor"] == pytest.approx(1.51)


def test_range_narrows_with_consistent_observations():
    job = manifest()
    for _ in range(16):
        update_correction(job, predicted=10, actual=10)
    result = estimate_job(job)
    assert (result.high - result.seconds) / result.seconds == pytest.approx(0.0625)


def test_pixel_count_and_output_rate_affect_cost():
    normal = predict_segment(MEDIA, SETTINGS, 100)
    bigger = predict_segment(MEDIA, {**SETTINGS, "short_side": 2160}, 100)
    single = predict_segment(MEDIA, {**SETTINGS, "fps": "off"}, 100)
    assert bigger > normal > single
    fast = {**MEDIA, "cfr_fps": "60"}
    assert predict_segment(fast, SETTINGS, 100) == predict_segment(
        fast, {**SETTINGS, "fps": "off"}, 100
    )
    assert predict_segment(MEDIA, SETTINGS, 0) == 0


def test_passthrough_and_resize_presets_do_not_interpolate():
    for preset in ("passthrough", "resize"):
        settings = {**SETTINGS, "preset": preset}
        assert predict_segment(MEDIA, settings, 100) == predict_segment(
            MEDIA, {**settings, "fps": "off"}, 100
        )


def test_null_profile_costs_fall_back_and_remain_uncalibrated():
    profile = {
        "components": {
            name: {"seconds_per_pixel_frame": None}
            for name in ("decode", "color", "resize", "blend2x", "encode")
        }
    }
    result = estimate_job(manifest(), profile)
    assert result.seconds == estimate_job(manifest()).seconds
    assert not result.calibrated


def test_job_profile_is_used_by_default():
    job = manifest()
    job["machine_profile"] = {
        "components": {name: 0 for name in ("decode", "color", "resize", "blend2x", "encode")},
        "segment_overhead_seconds": 7,
    }
    result = estimate_job(job)
    assert result.calibrated
    assert result.seconds == 14


def test_sar_normalization_cost_is_included_for_passthrough():
    media = {**MEDIA, "display_width": 1440, "display_height": 1280, "sar": "2"}
    settings = {**SETTINGS, "preset": "passthrough", "fps": "off"}
    profile = {
        "components": {name: 0 for name in ("decode", "color", "encode", "blend2x")},
        "segment_overhead_seconds": 0,
    }
    profile["components"]["resize"] = 1e-7
    assert predict_segment(media, settings, 10, profile) == pytest.approx(1440 * 1280 * 10 * 1e-7)


@pytest.mark.parametrize("predicted,actual", [(0, 1), (1, -1), (float("nan"), 1)])
def test_reject_invalid_timings(predicted, actual):
    with pytest.raises(ValueError):
        update_correction(manifest(), predicted, actual)
