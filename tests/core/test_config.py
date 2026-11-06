"""Config tests — AT-CORE9 (non-local backend gate) + env overrides."""

from __future__ import annotations

import pytest

from manthan.core.config import BackendConfigError, RootConfig, load_config


@pytest.mark.unit
def test_defaults_and_config_hash_stable():
    c1 = RootConfig()
    c2 = RootConfig()
    assert c1.config_hash() == c2.config_hash()
    assert c1.models.backend == "ollama"
    assert c1.budget.allow_non_local_backend is False


@pytest.mark.unit
def test_at_core9_non_local_backend_refused(monkeypatch):
    """AT-CORE9: non-local backend without opt-in raises; opt-in allows it."""
    c = RootConfig()
    c.models.backend = "remote-paid"
    with pytest.raises(BackendConfigError):
        c.assert_backend_allowed()
    # explicit opt-in (CI never does this)
    c.budget.allow_non_local_backend = True
    c.assert_backend_allowed()  # no raise


@pytest.mark.unit
def test_env_override_backend(monkeypatch):
    monkeypatch.setenv("MANTHAN_BACKEND", "mock")
    cfg = load_config()
    assert cfg.models.backend == "mock"


@pytest.mark.unit
def test_env_override_non_local_raises(monkeypatch):
    monkeypatch.setenv("MANTHAN_BACKEND", "someremote")
    monkeypatch.delenv("MANTHAN_ALLOW_NON_LOCAL_BACKEND", raising=False)
    with pytest.raises(BackendConfigError):
        load_config()


@pytest.mark.unit
def test_load_root_yaml_resolves_subconfigs(monkeypatch, tmp_path):
    monkeypatch.setenv("MANTHAN_BACKEND", "mock")
    (tmp_path / "models.yaml").write_text("backend: ollama\nbase_url: http://localhost:11434\n")
    (tmp_path / "budget.yaml").write_text("max_tokens: 123\nallow_non_local_backend: false\n")
    (tmp_path / "root.yaml").write_text(
        "seed: 42\ndomains: [prompt, rag]\nmodels_file: models.yaml\nbudget_file: budget.yaml\n"
    )
    cfg = load_config(tmp_path / "root.yaml")
    assert cfg.seed == 42 and cfg.domains == ["prompt", "rag"]
    assert cfg.budget.max_tokens == 123
    assert cfg.models.backend == "mock"  # env override wins over file 'ollama'


@pytest.mark.unit
def test_extra_keys_rejected():
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        RootConfig(unknown_key=1)  # type: ignore[call-arg]
