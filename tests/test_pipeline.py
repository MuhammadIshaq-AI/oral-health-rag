from app.experiments import ExperimentConfig, RetrievalConfig
from app.llm.providers import FakeClient
from app.rag.pipeline import RagPipeline
from app.rag.prompt import DISCLAIMER


def _cfg() -> ExperimentConfig:
    return ExperimentConfig(
        retrieval=RetrievalConfig(mode="hybrid", min_dense_score=0.0, final_k=3)
    )


async def test_cited_answer(retriever) -> None:
    llm = FakeClient(responses=["Bleeding gums can be a sign of gum disease [1]."])
    ans = await RagPipeline(retriever, llm, _cfg()).answer("why do my gums bleed", [])
    assert ans.citations == [1] and not ans.refused and ans.text.endswith(DISCLAIMER)
    assert ans.rewritten_query == "why do my gums bleed"  # no history → no rewrite call
    assert len(llm.calls) == 1


async def test_rewrite_uses_history(retriever) -> None:
    llm = FakeClient(
        responses=["knocked out adult tooth storage in milk", "Store the tooth in milk [1]."]
    )
    history = [
        {"role": "user", "content": "my son's tooth got knocked out"},
        {"role": "assistant", "content": "Hold it by the crown [1]."},
    ]
    ans = await RagPipeline(retriever, llm, _cfg()).answer("how do I store it?", history)
    assert ans.rewritten_query == "knocked out adult tooth storage in milk"
    assert ans.hits[0].chunk.chunk_id == "healthdirect-knocked-out-tooth#00"


async def test_regenerates_then_falls_back(retriever) -> None:
    llm = FakeClient(
        responses=["You have gum disease.", "It sounds like you have gum disease [1]."]
    )
    ans = await RagPipeline(retriever, llm, _cfg()).answer("bleeding gums", [])
    assert ans.refused and ans.attempts == 2
    assert "fallback_no_guidance" in ans.validation_flags


async def test_regeneration_succeeds(retriever) -> None:
    llm = FakeClient(responses=["Brush more.", "Brush twice a day and floss daily [1]."])
    ans = await RagPipeline(retriever, llm, _cfg()).answer("bleeding gums", [])
    assert not ans.refused and ans.attempts == 2


async def test_low_confidence_skips_llm(retriever) -> None:
    llm = FakeClient()
    cfg = ExperimentConfig(retrieval=RetrievalConfig(mode="rerank", min_rerank_score=0.99))
    ans = await RagPipeline(retriever, llm, cfg).answer("best pizza in Melbourne", [])
    assert ans.refused and llm.calls == [] and "1800 022 222" in ans.text
