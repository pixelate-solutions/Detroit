import math

from app import demo_ai
from app.parsing import ParsedDocument, chunk_document
from app.search import merge_hybrid_results


def test_demo_embeddings_are_deterministic_and_normalised():
    a, b = demo_ai.embed(["standpipe attack line", "standpipe attack line"])
    assert a == b
    assert math.isclose(sum(v * v for v in a), 1.0, rel_tol=1e-6)
    near, far = demo_ai.embed(["standpipe hose line crew", "hydrant flow test"])
    dot = lambda x, y: sum(p * q for p, q in zip(x, y))  # noqa: E731
    assert dot(a, near) > dot(a, far)


def test_extractive_answer_quotes_and_cites_the_relevant_sentence():
    results = [
        {"title": "Pump test", "snippet": "Engine 3 delivered 1,500 gpm at 150 psi.", "document_id": 1, "page_number": 1},
        {"title": "SOP 204", "snippet": "204.3 Attack line. A minimum crew of four is required to advance the attack line.",
         "document_id": 2, "page_number": 1},
    ]
    answer = demo_ai.answer("What crew size is required to advance the attack line?", results)
    assert "A minimum crew of four is required to advance the attack line. [C2]" in answer
    assert "no language model was used" in answer


def test_extractive_answer_admits_when_records_do_not_help():
    results = [{"title": "Pump test", "snippet": "Engine 3 delivered 1,500 gpm.", "document_id": 1, "page_number": 1}]
    assert "do not contain a passage" in demo_ai.answer("Who approved the zoning variance?", results)


def test_reciprocal_rank_fusion_rewards_agreement_between_channels():
    keyword = [{"chunk_id": 1, "matched_by": "keyword"}, {"chunk_id": 2, "matched_by": "keyword"}]
    semantic = [{"chunk_id": 2, "matched_by": "semantic"}, {"chunk_id": 3, "matched_by": "semantic"}]
    merged = merge_hybrid_results(keyword, semantic, top_k=3)
    assert merged[0]["chunk_id"] == 2
    assert merged[0]["matched_by"] == "keyword+semantic"
    assert merged[0]["score"] == 1.0


def test_chunks_keep_their_source_page_numbers():
    parsed = ParsedDocument(full_text="", pages=["First page text. " * 10, "Second page text. " * 10], ocr_used=False)
    chunks = chunk_document(parsed)
    assert [chunk.page_number for chunk in chunks] == [1, 2]


def test_sentence_compare_pairs_revised_sentences():
    before = {"title": "Rev 1", "full_text": "Scope stays.\nA minimum crew of three is required."}
    after = {"title": "Rev 2", "full_text": "Scope stays.\nA minimum crew of four is required."}
    summary = demo_ai.compare_summary(before, after)
    assert "**Now:** A minimum crew of four is required." in summary
    assert "~~A minimum crew of three is required.~~" in summary
