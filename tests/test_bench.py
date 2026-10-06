"""Contract checks for benchmark report shape and safe model selection."""

from videoenhancer.bench.runner import MODEL_CATALOG, _bench_models


def test_model_candidates_have_sources_and_explicit_hash_state() -> None:
    results = _bench_models("all", gpu_available=True)
    assert set(results) == set(MODEL_CATALOG)
    for key, result in results.items():
        assert result["status"] == "skipped"
        assert result["source_url"].startswith("https://")
        assert result["weights_url"].startswith("https://")
        assert result["sha256"] == MODEL_CATALOG[key].get("sha256")
        if result["status"] == "skipped":
            assert result["reason"].strip()


def test_model_candidates_explain_missing_cuda() -> None:
    result = _bench_models("rife", gpu_available=False)["rife"]
    assert result["status"] == "skipped"
    assert "CUDA" in result["reason"]
