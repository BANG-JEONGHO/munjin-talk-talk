"""
doctor_response Lambda (v3 — Tool Use 적용)
─────────────────────────────────────────────
POST /doctor-response

Bedrock Converse API + Tool Use로 환자 안내문 변환의 JSON 안정성 확보.
Validator 2차 검증:
  - 의사 답변에 없는 새 의학 정보(약·수치·진단·치료 권유) 추가 차단
  - 차단 시 의사 답변 원문으로 폴백
"""

import os
import re
import json
import boto3
from datetime import datetime, timezone

bedrock = boto3.client('bedrock-runtime', region_name=os.environ.get('AWS_REGION', 'ap-northeast-2'))
ddb = boto3.client('dynamodb')

TABLE = os.environ.get('SESSIONS_TABLE', 'sessions')
CLAUDE_MODEL = os.environ.get('CLAUDE_MODEL_ID', 'anthropic.claude-3-5-haiku-20241022-v1:0')


# ────────────────────────────────────────────────
# Tool 정의 (Patient Guide Generator)
# ────────────────────────────────────────────────

TOOL_PATIENT_GUIDE = {
    'toolSpec': {
        'name': 'generate_patient_guide',
        'description': """의사 답변을 어르신 친화적 문장으로 재구성.
의학적 의미는 보존하되 어휘·문장 구조만 어르신용으로 변환.
새 의학 정보 추가 절대 금지 (Validator가 후검증).""",
        'inputSchema': {
            'json': {
                'type': 'object',
                'properties': {
                    'answer_simple': {
                        'type': 'array',
                        'items': {'type': 'string', 'maxLength': 40},
                        'minItems': 1,
                        'maxItems': 6,
                        'description': '한 문장당 30자 이내. 의학 용어는 일상 표현으로.'
                    },
                    'tts_emphasis_words': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': 'TTS에서 강조할 단어 (약 이름·기간 등)'
                    }
                },
                'required': ['answer_simple']
            }
        }
    }
}


PATIENT_GUIDE_PROMPT = """의사가 환자 질문에 답변한 내용을 60-70대 어르신이 이해할 수 있는
친화적 문장으로 재구성하세요.

의사 답변:
"{doctor_answer}"

환자 질문 (원본):
"{patient_question}"

규칙:
- 한 문장 30자 이내.
- 의학 용어 → 일상 표현 (예: 성분명 → 일반 명칭).
- 새 의학 정보 추가 절대 금지 (의사가 말하지 않은 내용은 어떤 형태로도 추가 X).
- 진단명·처방 권유·응급실 권유 표현 금지.
- 약 종류·복용 기간·수치는 의사 답변 그대로 보존.
- 톤: 친근하지만 존댓말 유지.

generate_patient_guide 도구를 호출하세요."""


# ────────────────────────────────────────────────
# Validator 2차 — 의사 답변에 없는 의학 정보 추가 차단
# ────────────────────────────────────────────────

def validate_patient_guide(doctor_answer, llm_sentences):
    """LLM 변환이 의사 답변의 의미 범위를 벗어났는지 검사"""
    errors = []

    # ── 1. 새 진단·처방 권유 단어 차단 ──
    NEW_MEDICAL_VERBS = [
        '진단', '확진', '검사 권유', '입원 권유',
        '응급실', '수술', '주사', '치료를 받으'
    ]
    for sent in llm_sentences:
        for term in NEW_MEDICAL_VERBS:
            if term in sent and term not in doctor_answer:
                errors.append(f'new_medical_term: {term}')

    # ── 2. 새 약 이름 추가 차단 ──
    DRUG_PATTERN = r'[가-힣]+(?:약|정|캡슐|시럽|크림|연고|주사)'
    doc_drugs = set(re.findall(DRUG_PATTERN, doctor_answer))
    for sent in llm_sentences:
        sent_drugs = set(re.findall(DRUG_PATTERN, sent))
        new_drugs = sent_drugs - doc_drugs
        if new_drugs:
            errors.append(f'new_drug_added: {new_drugs}')

    # ── 3. 새 수치 추가 차단 (5일, 하루 한 잔 등) ──
    NUMERIC_PATTERN = r'\d+\s*(?:일|주|개월|회|잔|알|mg|cc|밀리|밀그램)'
    doc_nums = set(re.findall(NUMERIC_PATTERN, doctor_answer))
    for sent in llm_sentences:
        sent_nums = set(re.findall(NUMERIC_PATTERN, sent))
        new_nums = sent_nums - doc_nums
        if new_nums:
            errors.append(f'new_numeric: {new_nums}')

    # ── 4. 새 질병명 추가 차단 ──
    DISEASE_PATTERN = r'(?:감기|독감|폐렴|결핵|기관지염|천식|COPD|코로나|비염|편도염)'
    doc_diseases = set(re.findall(DISEASE_PATTERN, doctor_answer))
    for sent in llm_sentences:
        sent_diseases = set(re.findall(DISEASE_PATTERN, sent))
        new_diseases = sent_diseases - doc_diseases
        if new_diseases:
            errors.append(f'new_disease: {new_diseases}')

    return (len(errors) == 0, errors)


# ────────────────────────────────────────────────
# Tool Use 호출
# ────────────────────────────────────────────────

def call_claude_with_tool(prompt, tool_spec):
    """Bedrock Converse API + toolChoice"""
    tool_name = tool_spec['toolSpec']['name']
    response = bedrock.converse(
        modelId=CLAUDE_MODEL,
        messages=[{'role': 'user', 'content': [{'text': prompt}]}],
        toolConfig={
            'tools': [tool_spec],
            'toolChoice': {'tool': {'name': tool_name}}
        },
        inferenceConfig={'temperature': 0.3, 'maxTokens': 1024}
    )
    for block in response['output']['message']['content']:
        if 'toolUse' in block:
            return block['toolUse']['input']
    return {}


# ────────────────────────────────────────────────
# Patient Guide 항목 생성
# ────────────────────────────────────────────────

def generate_patient_guide_item(question_summary, doctor_answer, original_question=None):
    """한 개 질문/답변 쌍에 대해 어르신용 변환"""
    prompt = PATIENT_GUIDE_PROMPT.format(
        doctor_answer=doctor_answer,
        patient_question=original_question or question_summary
    )

    try:
        parsed = call_claude_with_tool(prompt, TOOL_PATIENT_GUIDE)
    except Exception as e:
        print(f"[ERROR] LLM 호출 실패: {e}")
        return {
            'question': question_summary,
            'answer_simple': [doctor_answer],
            'tts_emphasis_words': [],
            '_fallback': True,
            '_fallback_reason': 'llm_call_failed'
        }

    sentences = parsed.get('answer_simple', [])

    # ── Validator 2차 ──
    is_valid, errors = validate_patient_guide(doctor_answer, sentences)

    if not is_valid:
        print(f"[REJECT] Validator 2차 차단: {errors}")
        return {
            'question': question_summary,
            'answer_simple': [doctor_answer],  # 폴백: 의사 답변 원문
            'tts_emphasis_words': [],
            '_validator_errors': errors,
            '_fallback': True,
            '_fallback_reason': 'validator_2nd_blocked'
        }

    return {
        'question': question_summary,
        'answer_simple': sentences,
        'tts_emphasis_words': parsed.get('tts_emphasis_words', []),
        '_fallback': False
    }


# ────────────────────────────────────────────────
# 메인 핸들러
# ────────────────────────────────────────────────

def handler(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
    except json.JSONDecodeError:
        return _resp(400, {'error': 'invalid_json'})

    session_id = body.get('session_id')
    reviewer_id = body.get('reviewer_id', 'unknown')
    answers = body.get('answers', [])
    additional_notes = body.get('additional_notes', '')

    if not session_id or not answers:
        return _resp(400, {'error': 'missing_required_fields'})

    # 1. doctor_review 객체 구성
    doctor_review = {
        'reviewed_at': datetime.now(timezone.utc).isoformat(),
        'reviewer_id': reviewer_id,
        'answers_to_patient_questions': answers,
        'additional_notes': additional_notes,
    }

    # 2. Patient Guide 생성 (각 질문별 Tool Use 호출)
    guide_items = []
    for ans in answers:
        item = generate_patient_guide_item(
            question_summary=ans['question_summary'],
            doctor_answer=ans['answer_text'],
            original_question=ans.get('original_quote'),
        )
        guide_items.append(item)

    patient_guide = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'items': guide_items,
        'delivery_options': ['screen', 'tts', 'sms_caregiver', 'print'],
    }

    # 3. DynamoDB 저장
    try:
        ddb.update_item(
            TableName=TABLE,
            Key={'session_id': {'S': session_id}},
            UpdateExpression='SET doctor_review = :dr, patient_guide = :pg',
            ExpressionAttributeValues={
                ':dr': {'S': json.dumps(doctor_review, ensure_ascii=False)},
                ':pg': {'S': json.dumps(patient_guide, ensure_ascii=False)},
            }
        )
    except Exception as e:
        return _resp(500, {'error': 'ddb_update_failed', 'detail': str(e)})

    validator_passed = all(not item.get('_fallback', False) for item in guide_items)
    fallback_count = sum(1 for item in guide_items if item.get('_fallback', False))

    return _resp(200, {
        'doctor_review_saved': True,
        'patient_guide_generated': True,
        'validator_passed': validator_passed,
        'fallback_count': fallback_count,
        'patient_guide': patient_guide,
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
