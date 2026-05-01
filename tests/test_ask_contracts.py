from atlas.ask.contracts import AskAtlasResponse, EvidenceCard, RetrievalRequest


def test_retrieval_request_defaults() -> None:
    req = RetrievalRequest(query="bench frequency")
    assert req.max_sources == 8
    assert req.max_programs == 20


def test_ask_response_contract() -> None:
    response = AskAtlasResponse(
        answer="Most strong bench programs use 2-3 exposures per week.",
        confidence=0.72,
        evidence=[
            EvidenceCard(
                source_id=1,
                document_id=2,
                canonical_url="https://example.com/how-to-bench",
                snippet="Bench is trained 3x/week in this template.",
            )
        ],
    )
    dumped = response.model_dump()
    assert dumped["status"] == "ok"
    assert dumped["evidence"][0]["source_id"] == 1
