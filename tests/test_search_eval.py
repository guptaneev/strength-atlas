from atlas.db.models import Document, Source
from atlas.search import evaluation
from atlas.search.evaluation import load_eval_suite, run_search_eval_suite


def test_load_eval_suite_reads_queries(tmp_path) -> None:
    fixture = tmp_path / "eval.json"
    fixture.write_text(
        """{
  "queries": [
    {
      "name": "Bench",
      "mode": "sources",
      "query": "bench",
      "must_include_canonical_urls": ["https://example.com/bench"]
    }
  ]
}""",
        encoding="utf-8",
    )
    suite = load_eval_suite(str(fixture))
    assert len(suite) == 1
    assert suite[0].name == "Bench"
    assert suite[0].mode == "sources"


def test_run_search_eval_suite_computes_pass_rate(monkeypatch) -> None:
    class _Row:
        def __init__(self, document_id):
            self.document_id = document_id

    class _Session:
        def get(self, cls, obj_id):
            if cls is Document and obj_id == 1:
                return Document(id=1, source_id=2)
            if cls is Source and obj_id == 2:
                return Source(id=2, canonical_url="https://example.com/bench", domain_id=1)
            return None

    monkeypatch.setattr(evaluation, "search_programs", lambda *_args, **_kwargs: [_Row(document_id=1)])
    monkeypatch.setattr(
        evaluation,
        "search_sources",
        lambda *_args, **_kwargs: [Source(id=3, canonical_url="https://example.com/source", domain_id=1)],
    )

    suite = [
        evaluation.SearchEvalQuery(
            name="Programs",
            mode="programs",
            query="bench",
            top_k=10,
            filters={},
            must_include_canonical_urls=["https://example.com/bench"],
        ),
        evaluation.SearchEvalQuery(
            name="Sources",
            mode="sources",
            query="bench",
            top_k=10,
            filters={},
            must_include_canonical_urls=["https://example.com/source"],
        ),
    ]
    summary = run_search_eval_suite(_Session(), suite)
    assert summary["queries_total"] == 2
    assert summary["queries_passed"] == 2
    assert summary["pass_rate"] == 1.0
