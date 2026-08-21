import json

from scripts.evaluate_answer_models import build_prompt, load_test_queries


class FakeTokenizer:
    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=True):
        return messages[-1]["content"]


def test_load_test_queries_deduplicates_by_query(tmp_path):
    path = tmp_path / "split.json"
    path.write_text(json.dumps({"label_source": "human", "pairs": [
        {"query_id": "q1", "query": "one", "evidence": []},
        {"query_id": "q1", "query": "one", "evidence": []},
        {"query_id": "q2", "query": "two", "evidence": []},
    ]}))
    assert [row["query_id"] for row in load_test_queries(path)] == ["q1", "q2"]


def test_build_prompt_includes_evidence_ids_and_question():
    prompt = build_prompt({"query": "How?", "evidence": [{"evidence_id": "e1", "text": "Do this."}]}, FakeTokenizer())
    assert "[e1] Do this." in prompt
    assert "Question: How?" in prompt
