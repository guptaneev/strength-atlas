from atlas.api.schemas import ProgramSearchItem, SourceSearchItem
from atlas.db.models import Document, Program, Source
from atlas.ml.inference import rerank_program_items, rerank_source_items


class _KeywordReranker:
    def score(self, query, candidates):
        return [1.0 if query.lower() in candidate.text.lower() else 0.0 for candidate in candidates]


class _Session:
    def __init__(self, rows):
        self.rows = rows

    def get(self, model, row_id):
        return self.rows.get((model, row_id))


def test_reranks_program_items_without_losing_identifiers() -> None:
    source = Source(id=1, url="https://example.com", canonical_url="https://example.com", domain_id=1)
    document = Document(id=10, source_id=1, raw_text="training")
    advanced = Program(id=20, document_id=10, name="advanced plan")
    beginner = Program(id=21, document_id=10, name="beginner plan")
    session = _Session({(Source, 1): source, (Document, 10): document, (Program, 20): advanced, (Program, 21): beginner})
    items = [
        ProgramSearchItem(id=20, document_id=10, source_id=1),
        ProgramSearchItem(id=21, document_id=10, source_id=1),
    ]
    ranked = rerank_program_items(session, "beginner", items, _KeywordReranker())
    assert [item.id for item in ranked] == [21, 20]


def test_reranks_source_evidence_and_preserves_provenance() -> None:
    generic = Source(id=1, url="https://one.example", canonical_url="https://one.example", domain_id=1, latest_document_id=10)
    bench = Source(id=2, url="https://two.example", canonical_url="https://two.example", domain_id=1, latest_document_id=11)
    session = _Session({
        (Source, 1): generic,
        (Source, 2): bench,
        (Document, 10): Document(id=10, source_id=1, raw_text="general strength"),
        (Document, 11): Document(id=11, source_id=2, raw_text="bench frequency"),
    })
    items = [SourceSearchItem(id=1, canonical_url=generic.canonical_url), SourceSearchItem(id=2, canonical_url=bench.canonical_url)]
    ranked = rerank_source_items(session, "bench", items, _KeywordReranker())
    assert [item.id for item in ranked] == [2, 1]
    assert ranked[0].canonical_url == "https://two.example"
