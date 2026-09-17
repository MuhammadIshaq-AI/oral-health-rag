from app.rag.fusion import reciprocal_rank_fusion


def test_rrf_scores_and_order() -> None:
    fused = dict(reciprocal_rank_fusion([["a", "b", "c"], ["b", "a", "d"]], k=60))
    assert fused["a"] == fused["b"] == 1 / 61 + 1 / 62
    assert fused["c"] == 1 / 63 and fused["d"] == 1 / 63
    order = [d for d, _ in reciprocal_rank_fusion([["x", "y"], ["y"]], k=60)]
    assert order == ["y", "x"]


def test_rrf_empty() -> None:
    assert reciprocal_rank_fusion([[], []]) == []


def test_rrf_single_list_preserves_order() -> None:
    assert [d for d, _ in reciprocal_rank_fusion([["p", "q", "r"]])] == ["p", "q", "r"]
