from pathlib import Path

from app.experiments import config_hash, load_experiment

ROOT = Path(__file__).resolve().parents[1]


def test_extends_and_hash_stability() -> None:
    base = load_experiment(ROOT / "configs/default.yaml")
    gem = load_experiment(ROOT / "configs/gemini-flash.yaml")
    dense = load_experiment(ROOT / "configs/dense.yaml")
    assert gem.llm.provider == "gemini" and gem.retrieval.final_k == base.retrieval.final_k
    assert dense.retrieval.mode == "dense" and dense.llm.provider == "gemini"
    assert len({base.config_hash, gem.config_hash, dense.config_hash}) == 3
    assert load_experiment(ROOT / "configs/gemini-flash.yaml").config_hash == gem.config_hash


def test_config_hash_is_order_independent() -> None:
    assert config_hash({"a": 1, "b": {"c": 2, "d": 3}}) == config_hash(
        {"b": {"d": 3, "c": 2}, "a": 1}
    )


def test_all_configs_load() -> None:
    for path in (ROOT / "configs").glob("*.yaml"):
        assert load_experiment(path).name
