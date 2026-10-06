#!/usr/bin/env bash
set -euo pipefail

URL="${1:?Usage: smoke-api.sh URL}"
health=$(curl -fsS --retry 12 --retry-delay 5 --retry-connrefused --max-time 120 "$URL/health")
test "$(jq -r .token_contract_version <<<"$health")" = "2"
test "$(jq -r .capabilities.lossless_surface <<<"$health")" = "true"
test "$(jq -r .capabilities.english_reading <<<"$health")" = "true"
test "$(jq -r .candidate_contract_version <<<"$health")" = "1"
test "$(jq -r .capabilities.reading_nbest <<<"$health")" = "true"
yomi=$(curl -fsS --max-time 120 -X POST "$URL/yomi" -H 'Content-Type: application/json' \
  -d '{"text":"夕焼小焼"}' | jq -r .yomi)
test "$yomi" = "ユウヤケコヤケ"
english=$(curl -fsS --max-time 120 -X POST "$URL/tokenize" -H 'Content-Type: application/json' \
  -d '{"text":"I love you"}')
test "$(jq -r '[.tokens[].surface_form] | join("")' <<<"$english")" = "I love you"
test "$(jq -r '[.tokens[].pronunciation] | join("")' <<<"$english")" = "アイラヴユー"
candidates=$(curl -fsS --max-time 120 -X POST "$URL/yomi_candidates" -H 'Content-Type: application/json' \
  -d '{"text":"AI 4443","nbest":8}')
test "$(jq -r '.candidates[0].rank' <<<"$candidates")" = "0"
test "$(jq -r '[.candidates[].reading] | index("エーアイヨンヨンヨンサン") != null' \
  <<<"$candidates")" = "true"
echo "API smoke checks passed"
