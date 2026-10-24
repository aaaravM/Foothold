"""Career-fit model (brief 6.1): sample generator, cosine baseline, artifact round trip, predict shape."""

from __future__ import annotations

import numpy as np
import pytest

from foothold import career_fit as cf
from foothold import data


def test_occupation_table_shapes():
    traits, occs, W = cf.occupation_table()
    assert len(traits) == 21 and W.shape == (len(occs), 21)
    assert len(occs) >= 40
    assert len(cf.career_index(occs)) == 8
    assert W.min() >= 0 and W.max() <= 1


def test_make_samples_noise_and_dropout():
    _, _, W = cf.occupation_table()
    X, y = cf.make_samples(W, 20, np.random.default_rng(0))
    assert X.shape == (20 * len(W), 21) and y.shape == (20 * len(W),)
    assert X.min() >= 0 and X.max() <= 1
    assert (X == 0.5).mean() > 0.05  # dropout toward 0.5 happens
    X2, _ = cf.make_samples(W, 20, np.random.default_rng(0))
    assert np.array_equal(X, X2)  # seeded


def test_cosine_baseline_recovers_clean_profiles():
    _, occs, W = cf.occupation_table()
    S = cf.cosine_scores(W, W)
    assert (S.argmax(axis=1) == np.arange(len(occs))).mean() == 1.0


def _profile(career_id: str) -> dict[str, float]:
    return dict(data.get_career(career_id)["work_styles"])


def test_predict_cosine_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(cf, "ARTIFACT_PT", tmp_path / "missing.pt")
    out = cf.predict(_profile("registered_nurse"), k=3)
    assert out["model"] == "cosine" and out["trained"] is False
    assert len(out["top"]) == 3 and out["top"][0]["career_id"] == "registered_nurse"
    assert abs(sum(o["probability"] for o in out["occupations"]) - 1) < 1e-3
    assert len(out["occupations"]) == len(cf.occupation_table()[1])
    assert set(out["top"][0]) >= {"career_id", "title", "probability", "p_overall", "onet_soc"}


def test_predict_handles_partial_and_list_input(monkeypatch, tmp_path):
    monkeypatch.setattr(cf, "ARTIFACT_PT", tmp_path / "missing.pt")
    assert cf.predict({"empathy": 0.9, "bogus": "x"})["top"]
    assert cf.predict([0.5] * 21, k=8)["top"].__len__() == 8
    with pytest.raises(ValueError):
        cf.to_vector([0.5] * 3)


def test_state_dict_round_trip_weights_only(monkeypatch, tmp_path):
    torch = pytest.importorskip("torch")
    import json

    traits, occs, W = cf.occupation_table()
    torch.manual_seed(0)
    model = cf.build_mlp(len(traits), len(occs))
    pt, js = tmp_path / "cf.pt", tmp_path / "cf.json"
    torch.save(model.state_dict(), pt)
    js.write_text(json.dumps({"trait_order": traits, "classes": [o["onet_soc"] for o in occs], "hidden": list(cf.HIDDEN),
                              "dropout": 0.1}), encoding="utf-8")
    monkeypatch.setattr(cf, "ARTIFACT_PT", pt)
    monkeypatch.setattr(cf, "ARTIFACT_JSON", js)
    out = cf.predict(_profile("welder"))
    assert out["model"] == "mlp" and out["trained"] is True
    expected = cf.mlp_proba(model, cf.to_vector(_profile("welder")))[0]
    assert abs(out["occupations"][0]["probability"] - round(float(expected.max()), 4)) < 1e-4
    # mismatched class order -> falls back to cosine instead of crashing
    js.write_text(json.dumps({"trait_order": traits, "classes": ["x"], "hidden": list(cf.HIDDEN)}), encoding="utf-8")
    import os, time
    os.utime(js, (time.time() + 5, time.time() + 5))
    assert cf.predict(_profile("welder"))["model"] == "cosine"


def test_trained_artifact_if_present():
    if not cf.ARTIFACT_PT.exists():
        pytest.skip("run ml/train_career_fit.py first")
    out = cf.predict(_profile("software_dev"))
    assert out["model"] == "mlp" and out["top"][0]["career_id"] == "software_dev"
