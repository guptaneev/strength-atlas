from atlas.api.traces import append_retrieval_trace


def test_append_retrieval_trace_writes_jsonl(tmp_path) -> None:
    path = tmp_path / "retrieval-debug.jsonl"
    append_retrieval_trace(str(path), {"query": "bench", "count": 2})
    text = path.read_text(encoding="utf-8").strip()
    assert '"query": "bench"' in text
    assert '"count": 2' in text
