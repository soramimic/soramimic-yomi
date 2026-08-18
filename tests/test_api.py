import sys
from pathlib import Path

from fastapi.testclient import TestClient

# uv's package test environment does not automatically put the repository root
# (which contains the deployment-only api module) on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api.main import app


client = TestClient(app)


def test_health_advertises_lossless_english_contract():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "token_contract_version": 2,
        "capabilities": {
            "lossless_surface": True,
            "english_reading": True,
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
