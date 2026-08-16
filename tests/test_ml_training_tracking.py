"""Unit tests for the optional, non-serving W&B integration."""

from __future__ import annotations

import sys
from types import ModuleType

from atlas.ml.training import ExperimentTrackingConfig, _log_wandb_report_artifact, _start_wandb_run


def test_wandb_tracking_is_disabled_by_default() -> None:
    assert _start_wandb_run(ExperimentTrackingConfig(), {"seed": 42}) is None


def test_wandb_run_and_report_artifact_are_configured(monkeypatch, tmp_path) -> None:
    calls: dict[str, object] = {}

    class _Artifact:
        def __init__(self, name, type):
            calls["artifact"] = (name, type)

        def add_file(self, path, name):
            calls["artifact_file"] = (path, name)

    class _Run:
        def log_artifact(self, artifact):
            calls["logged_artifact"] = artifact

    fake_wandb = ModuleType("wandb")
    fake_wandb.init = lambda **kwargs: calls.setdefault("init", kwargs) and _Run()  # type: ignore[attr-defined]
    fake_wandb.Artifact = _Artifact  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "wandb", fake_wandb)

    run = _start_wandb_run(
        ExperimentTrackingConfig(project="strength-atlas", entity="team", run_name="reranker-v2", mode="offline"),
        {"seed": 42},
    )
    assert isinstance(run, _Run)
    assert calls["init"] == {
        "project": "strength-atlas",
        "entity": "team",
        "name": "reranker-v2",
        "mode": "offline",
        "job_type": "reranker-training",
        "tags": ["reranker", "cross-encoder"],
        "config": {"seed": 42},
    }
    report = tmp_path / "training-report.json"
    report.write_text("{}", encoding="utf-8")
    _log_wandb_report_artifact(run, report)
    assert calls["artifact"] == ("reranker-training-report", "reranker-evaluation")
    assert calls["artifact_file"] == (str(report), "training-report.json")
