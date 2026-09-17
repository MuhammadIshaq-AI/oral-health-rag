from app.experiments import RetrievalConfig
from app.rag.bm25 import tokenize


def test_modes_find_relevant_chunk(retriever) -> None:
    for mode in ("dense", "hybrid", "rerank"):
        cfg = RetrievalConfig(mode=mode, final_k=3, min_dense_score=0.0, min_rerank_score=0.0)
        res = retriever.retrieve("my gums are bleeding when I brush", cfg)
        assert res.hits[0].chunk.chunk_id == "healthdirect-bleeding-gums#00", mode


def test_hybrid_scores_recorded(retriever) -> None:
    res = retriever.retrieve(
        "child dental benefits schedule", RetrievalConfig(mode="hybrid", final_k=2)
    )
    top = res.hits[0]
    assert top.chunk.chunk_id == "healthdirect-public-dental#00"
    assert top.rrf is not None and top.bm25 is not None and top.dense is not None
    assert set(top.log_record()) == {"chunk_id", "url", "dense", "bm25", "rrf", "rerank"}


def test_confidence_gate(retriever) -> None:
    cfg = RetrievalConfig(mode="rerank", min_rerank_score=0.9)
    assert not retriever.retrieve("quantum chromodynamics lattice", cfg).confident


def test_exclude_secondary(retriever) -> None:
    cfg = RetrievalConfig(mode="hybrid", include_secondary=False, final_k=10)
    ids = [h.chunk.chunk_id for h in retriever.retrieve("oral diseases worldwide", cfg).hits]
    assert "who-oral-health#00" not in ids


def test_tokenize_folds_plurals_and_stopwords() -> None:
    assert tokenize("The babies' teeth are bleeding") == ["baby", "teeth", "bleeding"]
