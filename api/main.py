"""soramimic-yomi の読み推定API(FastAPI)。

- POST /yomi     : テキスト(または配列)の読みを返す(正規化ルール適用)
- POST /tokenize : kuromoji.js互換のトークン列を返す(表層は保持)
- GET  /health   : ヘルスチェック(利用側のフォールバック判定用)
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import soramimic_yomi

app = FastAPI(title="soramimic-yomi")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class TextRequest(BaseModel):
    text: str | list[str]


class CandidatesRequest(TextRequest):
    nbest: int = Field(default=8, ge=1, le=32)


@app.get("/health")
def health() -> dict:
    return {
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


@app.post("/yomi")
def yomi(req: TextRequest) -> dict:
    if isinstance(req.text, list):
        return {"yomi": [soramimic_yomi.get_yomi(t) for t in req.text]}
    return {"yomi": soramimic_yomi.get_yomi(req.text)}


@app.post("/yomi_candidates")
def yomi_candidates(req: CandidatesRequest) -> dict:
    def candidates(text: str) -> list[dict]:
        return [
            candidate.to_dict()
            for candidate in soramimic_yomi.get_yomi_candidates(text, nbest=req.nbest)
        ]

    if isinstance(req.text, list):
        return {"candidates": [candidates(text) for text in req.text]}
    return {"candidates": candidates(req.text)}


@app.post("/tokenize")
def tokenize(req: TextRequest) -> dict:
    if isinstance(req.text, list):
        return {"tokens": [soramimic_yomi.get_tokens(t) for t in req.text]}
    return {"tokens": soramimic_yomi.get_tokens(req.text)}
