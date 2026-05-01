import json

from atlas.ops.ledger import append_run_record, read_recent_run_records


def test_append_and_read_recent_records(tmp_path) -> None:
    path = tmp_path / "runs.jsonl"
    append_run_record(str(path), {"run_id": "1", "totals": {"processed": 1}})
    append_run_record(str(path), {"run_id": "2", "totals": {"processed": 2}})

    rows = read_recent_run_records(str(path), limit=1)
    assert len(rows) == 1
    assert rows[0]["run_id"] == "2"


def test_read_recent_skips_invalid_json_lines(tmp_path) -> None:
    path = tmp_path / "runs.jsonl"
    path.write_text('{"run_id":"1"}\nnot-json\n{"run_id":"2"}\n', encoding="utf-8")
    rows = read_recent_run_records(str(path), limit=10)
    assert [row["run_id"] for row in rows] == ["1", "2"]


def test_append_writes_json_line(tmp_path) -> None:
    path = tmp_path / "runs.jsonl"
    append_run_record(str(path), {"run_id": "abc", "totals": {"failed": 0}})
    line = path.read_text(encoding="utf-8").strip()
    parsed = json.loads(line)
    assert parsed["run_id"] == "abc"
