"""
validate_output Lambda
───────────────────────
POST /validate

extract + match 결과를 받아 4단 검증 후 DynamoDB에 저장.

검증 단계:
1. JSON Schema 일치
2. source_quote 원문 일치 (이미 extract 단계에서 1차 검증됨, 재확인)
3. 위험 키워드 감지 → safety_flag 설정
4. 금지 출력 패턴 (진단·처방 단어) 차단

요청 페이로드:
{
  "session_id": "s-xxx",
  "question_id": "Q1",
  "visit_type": "initial",
  "transcript": "어제부터 목이 칼칼하고...",
  "question_type": "chief_complaint",
  "spans": [...],
  "matched_slots": [...],  // Q1만
  "structured": {...}      // Q2-Q4 구조화 데이터
}

응답 페이로드:
{
  "validator_passed": true,
  "errors": [],
  "safety_flag": null | { ... },
  "saved": true
}
"""

import os
import re
import json
import boto3
from datetime import datetime, timezone
from pathlib import Path

ddb = boto3.client('dynamodb')
TABLE = os.environ.get('SESSIONS_TABLE', 'sessions')


def _load_json(filename):
    """data 파일 로드 (/opt/data 우선)"""
    for p in [Path('/opt/data') / filename, Path(__file__).parent / filename]:
        if p.exists():
            with open(p, encoding='utf-8') as f:
                return json.load(f)
    return {}


SAFETY_KEYWORDS = _load_json('safety_keywords.json')
FORBIDDEN_OUTPUTS = _load_json('forbidden_outputs.json')


# ─────────────────────────────────
# 검증 함수
# ─────────────────────────────────
def validate_source_quotes(spans, transcript):
    """모든 span의 source_quote가 원문에 존재하는지"""
    errors = []
    for span in spans:
        sq = span.get('source_quote', '')
        if sq and sq not in transcript:
            errors.append(f'source_quote_not_in_transcript: {sq}')
    return errors


def detect_safety_keywords(transcript):
    """위험 키워드 감지"""
    if not SAFETY_KEYWORDS:
        return None

    for category, config in SAFETY_KEYWORDS.items():
        if isinstance(config, dict):
            patterns = config.get('patterns', [])
            severity = config.get('severity', 'medium')
            label = config.get('label', category)
            action = config.get('action', 'review_priority')
        else:
            patterns = config if isinstance(config, list) else []
            severity = 'medium'
            label = category
            action = 'review_priority'

        for pattern in patterns:
            # 단순 substring 매칭 (False positive 방지를 위해 정밀 패턴 사용 가능)
            if pattern in transcript:
                # 추가 검증: "피곤하다"가 "피"에 매칭되는 false positive 방지
                if pattern == '피' and ('피곤' in transcript or '피로' in transcript):
                    continue
                return {
                    'category': category,
                    'label': label,
                    'severity': severity,
                    'matched_pattern': pattern,
                    'action': action,
                }
    return None


def check_forbidden_patterns(text):
    """진단·처방 단어 차단 패턴 검사"""
    errors = []
    forbidden_list = FORBIDDEN_OUTPUTS.get('patterns', []) if isinstance(FORBIDDEN_OUTPUTS, dict) else []
    for pattern in forbidden_list:
        if re.search(pattern, text):
            errors.append(f'forbidden_pattern: {pattern}')
    return errors


# ─────────────────────────────────
# 페이로드 조립
# ─────────────────────────────────
def build_q_payload(question_type, visit_type, transcript, spans, matched_slots, structured):
    """질문별 페이로드를 DDB 저장 형식으로 구성"""
    base = {
        'type': question_type,
        'raw_transcript': transcript,
        'confirmed': True,
        'spans': spans,
    }

    if question_type == 'chief_complaint':
        base['matched_slots'] = matched_slots
    elif question_type == 'progress':
        base['matched_slots'] = matched_slots
        # progress_summary 자동 생성
        summary = {'improved': [], 'unchanged': [], 'worsened': [], 'new': []}
        for span in spans:
            stype = span.get('type', '')
            slot_ref = span.get('slot_ref')
            if not slot_ref:
                continue
            if stype == 'progress_improved':
                summary['improved'].append(slot_ref)
            elif stype == 'progress_unchanged':
                summary['unchanged'].append(slot_ref)
            elif stype == 'progress_worsened':
                summary['worsened'].append(slot_ref)
            elif stype == 'new_symptom':
                summary['new'].append(slot_ref)
        base['progress_summary'] = summary
    elif question_type in ('onset', 'adherence'):
        base.update(structured or {})
    elif question_type == 'current_medications':
        base.update(structured or {})
    elif question_type == 'new_symptoms':
        base.update(structured or {})
    elif question_type in ('patient_questions', 'unresolved_questions'):
        base['questions'] = (structured or {}).get('questions', [])

    return base


# ─────────────────────────────────
# 메인 핸들러
# ─────────────────────────────────
def handler(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
    except json.JSONDecodeError:
        return _resp(400, {'error': 'invalid_json'})

    session_id = body.get('session_id')
    question_id = body.get('question_id')
    question_type = body.get('question_type')
    visit_type = body.get('visit_type', 'initial')
    transcript = body.get('transcript', '')
    spans = body.get('spans', [])
    matched_slots = body.get('matched_slots', [])
    structured = body.get('structured', {})

    if not all([session_id, question_id, question_type, transcript]):
        return _resp(400, {'error': 'missing_required_fields'})

    # ─── 1. JSON Schema 검증 ───
    errors = []
    if not isinstance(spans, list):
        errors.append('spans_not_list')
    if matched_slots and not isinstance(matched_slots, list):
        errors.append('matched_slots_not_list')

    # ─── 2. source_quote 원문 일치 ───
    errors.extend(validate_source_quotes(spans, transcript))

    # ─── 3. 위험 키워드 감지 ───
    safety_flag = detect_safety_keywords(transcript)

    # ─── 4. 금지 출력 패턴 ───
    # matched_slots, structured 등 출력될 모든 텍스트 검사
    output_text = json.dumps({
        'matched_slots': matched_slots,
        'structured': structured,
    }, ensure_ascii=False)
    errors.extend(check_forbidden_patterns(output_text))

    validator_passed = len(errors) == 0

    # ─── 5. DDB 저장 ───
    payload = build_q_payload(question_type, visit_type, transcript, spans, matched_slots, structured)

    try:
        update_expr = 'SET responses.#qid = :payload'
        expr_attr_names = {'#qid': question_id}
        expr_attr_values = {':payload': {'S': json.dumps(payload, ensure_ascii=False)}}

        if safety_flag:
            update_expr += ', safety_flag = :sf'
            expr_attr_values[':sf'] = {'S': json.dumps(safety_flag, ensure_ascii=False)}

        update_expr += ', validator_passed = :vp, completed_at = :ca'
        expr_attr_values[':vp'] = {'BOOL': validator_passed}
        expr_attr_values[':ca'] = {'S': datetime.now(timezone.utc).isoformat()}

        ddb.update_item(
            TableName=TABLE,
            Key={'session_id': {'S': session_id}},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_attr_names,
            ExpressionAttributeValues=expr_attr_values,
        )
        saved = True
    except Exception as e:
        print(f"[ERROR] DDB save failed: {e}")
        saved = False
        errors.append(f'ddb_save_failed: {str(e)}')

    return _resp(200, {
        'validator_passed': validator_passed,
        'errors': errors,
        'safety_flag': safety_flag,
        'saved': saved,
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
