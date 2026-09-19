import sys
from importlib import import_module
from pathlib import Path

from fastapi.testclient import TestClient

# uv's package test environment does not automatically put the repository root
# (which contains the deployment-only api module) on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
app = import_module("api.main").app


client = TestClient(app)


def test_health_advertises_lossless_english_contract():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "token_contract_version": 2,
        "candidate_contract_version": 1,
        "capabilities": {
            "lossless_surface": True,
            "english_reading": True,
            "reading_nbest": True,
            "connected_english": True,
            "structured_readings": True,
        },
    }


def test_tokenize_english_is_lossless_and_readable():
    response = client.post("/tokenize", json={"text": "I love you"})

    assert response.status_code == 200
    tokens = response.json()["tokens"]
    assert "".join(t["surface_form"] for t in tokens) == "I love you"
    assert "".join(t["pronunciation"] for t in tokens) == "アイラヴユー"
    assert tokens[0]["pos"] == "名詞"
    assert tokens[0]["is_silent"] is False


def test_tokenize_array_keeps_response_envelope_and_per_input_shape():
    inputs = [" Hello  world ", "don't stop", "don’t stop", "   ", "海、I!"]
    response = client.post("/tokenize", json={"text": inputs})

    assert response.status_code == 200
    token_lists = response.json()["tokens"]
    assert len(token_lists) == len(inputs)
    for text, tokens in zip(inputs, token_lists, strict=True):
        assert "".join(t["surface_form"] for t in tokens) == text

    assert token_lists[1][0]["pronunciation"] == token_lists[2][0]["pronunciation"]
    assert "".join(t["pronunciation"] for t in token_lists[4]) == "ウミアイ"


def test_yomi_response_envelope_is_unchanged():
    assert client.post("/yomi", json={"text": "I love you"}).json() == {
        "yomi": "アイラヴユー"
    }
    assert client.post("/yomi", json={"text": ["海", "Hello"]}).json() == {
        "yomi": ["ウミ", "ハロー"]
    }


def test_yomi_candidates_returns_structured_ranked_results():
    response = client.post("/yomi_candidates", json={"text": "AI 4443", "nbest": 8})

    assert response.status_code == 200
    candidates = response.json()["candidates"]
    assert candidates[0]["reading"] == "アイヨンセンヨンヒャクヨンジューサン"
    assert candidates[0] == {
        "reading": candidates[0]["reading"],
        "rank": 0,
        "cost": 0.0,
        "sources": ["canonical"],
        "spans": [],
    }
    assert [candidate["rank"] for candidate in candidates] == list(
        range(len(candidates))
    )
    assert any(candidate["spans"] for candidate in candidates[1:])


def test_yomi_candidates_array_preserves_per_input_shape():
    response = client.post("/yomi_candidates", json={"text": ["海", "AI"], "nbest": 3})

    assert response.status_code == 200
    candidates = response.json()["candidates"]
    assert candidates[0][0]["reading"] == "ウミ"
    assert candidates[1][0]["reading"] == "アイ"
    assert any(item["reading"] == "エーアイ" for item in candidates[1])


def test_yomi_candidates_includes_compact_english_with_default_limit():
    response = client.post("/yomi_candidates", json={"text": "shout it out"})
    assert response.status_code == 200
    readings = [candidate["reading"] for candidate in response.json()["candidates"]]
    assert readings[0] == "シャウトイットアウト"
    assert "シャティタ" in readings


def test_yomi_candidates_rejects_out_of_range_nbest():
    assert (
        client.post("/yomi_candidates", json={"text": "AI", "nbest": 0}).status_code
        == 422
    )
