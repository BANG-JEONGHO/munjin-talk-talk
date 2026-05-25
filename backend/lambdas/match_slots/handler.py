"""
match_slots Lambda
───────────────────
POST /match

Bedrock Titan Embed v2로 환자 발화의 span을 벡터로 변환하고,
미리 캐싱된 슬롯 카드 임베딩과 cosine similarity로 매칭.

콜드 스타트 시 슬롯 카드 87개의 임베딩을 1회만 계산하여
글로벌 변수에 캐시 (warm invocation에서는 재사용).

요청 페이로드:
{
  "session_id": "s-xxx",
  "question_id": "Q1",
  "visit_type": "initial",
  "spans": [
    {"source_quote": "목이 칼칼하고", "type": "symptom"},
    {"source_quote": "코가 맥혀요", "type": "symptom"}
  ]
}

응답 페이로드:
{
  "matched_slots": [
    {"slot_id": "throat_irritation", "name": "목 불편감",
     "score": 0.91, "source_quote": "목이 칼칼하고"},
    ...
  ],
  "unmatched_spans": [...]  // threshold 미달 span (의사가 직접 판단)
}
"""

import os
import json
import math
import boto3
from pathlib import Path

bedrock = boto3.client('bedrock-runtime', region_name=os.environ.get('AWS_REGION', 'ap-northeast-2'))
TITAN_MODEL = os.environ.get('TITAN_MODEL_ID', 'amazon.titan-embed-text-v2:0')

THRESHOLD = float(os.environ.get('MATCH_THRESHOLD', '0.75'))
TOP_K = 3

# 콜드 스타트 시 1회만 계산
SLOT_EMBEDDINGS = None
SLOT_CARDS = None


def _embed(text):
    """Bedrock Titan Embed로 텍스트를 1024차원 벡터로 변환"""
    response = bedrock.invoke_model(
        modelId=TITAN_MODEL,
        body=json.dumps({'inputText': text})
    )
    result = json.loads(response['body'].read())
    return result['embedding']


def _cosine(v1, v2):
    """cosine similarity (numpy 없이 순수 Python)"""
    dot = sum(a * b for a, b in zip(v1, v2))
    n1 = math.sqrt(sum(a * a for a in v1))
    n2 = math.sqrt(sum(b * b for b in v2))
    if n1 == 0 or n2 == 0:
        return 0.0
    return dot / (n1 * n2)


def _load_slot_cards():
    """slot_cards.json 로드"""
    global SLOT_CARDS
    if SLOT_CARDS is not None:
        return SLOT_CARDS

    # 우선순위: /opt/data (Lambda Layer) > 같은 디렉토리
    paths = [
        Path('/opt/data/slot_cards.json'),
        Path(__file__).parent / 'slot_cards.json',
    ]
    for p in paths:
        if p.exists():
            with open(p, encoding='utf-8') as f:
                data = json.load(f)
                SLOT_CARDS = data.get('slot_cards', [])
                return SLOT_CARDS
    return []


def _init_slot_embeddings():
    """콜드 스타트 시 87개 슬롯 임베딩 미리 계산"""
    global SLOT_EMBEDDINGS
    if SLOT_EMBEDDINGS is not None:
        return  # 이미 캐시됨 (warm invocation)

    slots = _load_slot_cards()
    SLOT_EMBEDDINGS = {}

    for slot in slots:
        slot_id = slot.get('slot_id')
        if not slot_id:
            continue

        # 정의 + positive_examples를 합쳐서 임베딩 (의미 공간 안정화)
        definition = slot.get('definition', '')
        examples = slot.get('positive_examples', [])
        text = f"{slot.get('canonical_name', '')}. {definition} {' '.join(examples)}"

        try:
            SLOT_EMBEDDINGS[slot_id] = {
                'name': slot.get('canonical_name', slot_id),
                'vector': _embed(text),
                'risk_level': slot.get('risk_level', 'normal'),
            }
        except Exception as e:
            print(f"[WARN] Slot {slot_id} embedding failed: {e}")

    print(f"[INIT] {len(SLOT_EMBEDDINGS)}/{len(slots)} slot embeddings cached")


def _match_single_span(span_text):
    """한 span을 모든 슬롯과 비교하여 Top-3 반환"""
    span_vec = _embed(span_text)
    scores = []
    for slot_id, slot_data in SLOT_EMBEDDINGS.items():
        score = _cosine(span_vec, slot_data['vector'])
        scores.append((slot_id, slot_data['name'], score))

    scores.sort(key=lambda x: -x[2])
    return scores[:TOP_K]


# ─────────────────────────────────
# 메인 핸들러
# ─────────────────────────────────
def handler(event, context):
    _init_slot_embeddings()  # 콜드 스타트 시만 실제 수행

    try:
        body = json.loads(event.get('body', '{}'))
    except json.JSONDecodeError:
        return _resp(400, {'error': 'invalid_json'})

    spans = body.get('spans', [])
    visit_type = body.get('visit_type', 'initial')

    if not spans:
        return _resp(200, {'matched_slots': [], 'unmatched_spans': []})

    matched = []
    unmatched = []

    for span in spans:
        # 매칭이 의미 있는 type만 처리
        # 초진: symptom
        # 재진: progress_*, new_symptom (slot_ref가 있을 수 있음)
        span_type = span.get('type', '')
        source_quote = span.get('source_quote', '')

        if not source_quote:
            continue

        # 재진의 경우 slot_ref가 LLM에서 이미 제공됨 → 그대로 사용
        if visit_type == 'followup' and span.get('slot_ref'):
            slot_id = span['slot_ref']
            if slot_id in SLOT_EMBEDDINGS:
                matched.append({
                    'slot_id': slot_id,
                    'name': SLOT_EMBEDDINGS[slot_id]['name'],
                    'score': 1.0,  # LLM 제공 → confidence 100%
                    'source_quote': source_quote,
                    'span_type': span_type,
                    'source': 'llm_provided',
                })
                continue

        # 일반 케이스: 벡터 매칭 수행 (초진 symptom 등)
        if span_type not in ('symptom', 'new_symptom', 'progress_improved',
                              'progress_unchanged', 'progress_worsened'):
            continue

        try:
            top_matches = _match_single_span(source_quote)
        except Exception as e:
            print(f"[ERROR] Match failed for '{source_quote}': {e}")
            continue

        if not top_matches:
            unmatched.append({'source_quote': source_quote, 'reason': 'no_candidates'})
            continue

        top1 = top_matches[0]
        if top1[2] >= THRESHOLD:
            matched.append({
                'slot_id': top1[0],
                'name': top1[1],
                'score': round(top1[2], 3),
                'source_quote': source_quote,
                'span_type': span_type,
                'top_alternatives': [
                    {'slot_id': m[0], 'name': m[1], 'score': round(m[2], 3)}
                    for m in top_matches[1:3]
                ],
                'source': 'vector_match',
            })
        else:
            unmatched.append({
                'source_quote': source_quote,
                'best_match': {'slot_id': top1[0], 'name': top1[1], 'score': round(top1[2], 3)},
                'reason': f'below_threshold_{THRESHOLD}',
            })

    return _resp(200, {
        'matched_slots': matched,
        'unmatched_spans': unmatched,
        'threshold_used': THRESHOLD,
    })


def _resp(status, body):
    return {
        'statusCode': status,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST,OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
        },
        'body': json.dumps(body, ensure_ascii=False)
    }
