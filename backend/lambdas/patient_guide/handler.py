"""
patient_guide Lambda
─────────────────────
GET /onepager/{session_id}    → 의사 원페이퍼 조회
GET /guide/{session_id}        → 환자 안내문 조회

DynamoDB에서 세션 데이터를 읽고 화면에 맞게 정리하여 반환.

GET /onepager 응답:
{
  "session_id": "...",
  "visit_type": "initial" | "followup",
  "patient": { ... },
  "agenda": [...],
  "symptom_card": { ... },         // 초진은 slots, 재진은 progress
  "review_items": [...],
  "transfer_text": "...",
  "safety_flag": { ... } | null
}

GET /guide 응답:
{
  "session_id": "...",
  "patient_name_masked": "김*자",
  "patient_guide": { ... },
  "doctor_additional_notes": "..."
}
"""

import os
import json
import boto3
from boto3.dynamodb.conditions import Key

ddb = boto3.client('dynamodb')
TABLE = os.environ.get('SESSIONS_TABLE', 'sessions')

# Mock 환자 데이터 (MVP - 실서비스는 HIS API 연동)
MOCK_PATIENT = {
    'A-0427': {
        'name_masked': '김*자',
        'age': 74,
        'gender': '여성',
        'receipt_id': 'A-0427',
        'department': '이비인후과',
    }
}


def handler(event, context):
    path = event.get('path', '')
    path_params = event.get('pathParameters') or {}
    session_id = path_params.get('session_id') or path_params.get('id')

    if not session_id:
        return _resp(400, {'error': 'missing_session_id'})

    # DynamoDB 조회
    try:
        result = ddb.get_item(
            TableName=TABLE,
            Key={'session_id': {'S': session_id}}
        )
    except Exception as e:
        return _resp(500, {'error': 'ddb_failed', 'detail': str(e)})

    if 'Item' not in result:
        return _resp(404, {'error': 'session_not_found'})

    session = _ddb_to_dict(result['Item'])

    # 라우팅: /onepager vs /guide
    if '/guide' in path:
        return _guide_response(session)
    else:
        return _onepager_response(session)


# ─────────────────────────────────
# 원페이퍼 조회 응답
# ─────────────────────────────────
def _onepager_response(session):
    visit_type = session.get('visit_type', 'initial')
    responses = session.get('responses', {})

    # 환자 정보 (mock)
    patient = MOCK_PATIENT.get('A-0427', {
        'name_masked': '환자',
        'age': 0,
        'gender': '-',
        'receipt_id': 'unknown',
        'department': '이비인후과',
    })

    # 환자 질문 카드 (Q4)
    q4 = responses.get('Q4') or {}
    agenda = q4.get('questions', [])

    # 증상 카드 (Q1)
    q1 = responses.get('Q1') or {}
    symptom_card = {}
    if visit_type == 'initial':
        symptom_card = {
            'type': 'symptom_list',
            'slots': q1.get('matched_slots', []),
        }
    else:
        symptom_card = {
            'type': 'progress_tracking',
            'progress_summary': q1.get('progress_summary', {}),
            'spans': q1.get('spans', []),
        }

    # 의료진 확인 항목 (사전 정의된 review_template 사용)
    review_items = _build_review_items(session)

    # 기록용 문장
    transfer_text = _build_transfer_text(session, patient)

    # 위험 플래그
    safety_flag = session.get('safety_flag')

    return _resp(200, {
        'session_id': session.get('session_id'),
        'visit_type': visit_type,
        'patient': patient,
        'agenda': agenda,
        'symptom_card': symptom_card,
        'review_items': review_items,
        'transfer_text': transfer_text,
        'safety_flag': safety_flag,
        'doctor_review': session.get('doctor_review'),
    })


# ─────────────────────────────────
# 환자 안내문 조회 응답
# ─────────────────────────────────
def _guide_response(session):
    patient_guide = session.get('patient_guide')
    if not patient_guide:
        return _resp(404, {'error': 'patient_guide_not_ready'})

    doctor_review = session.get('doctor_review', {})
    if isinstance(doctor_review, str):
        try:
            doctor_review = json.loads(doctor_review)
        except (json.JSONDecodeError, TypeError):
            doctor_review = {}

    if isinstance(patient_guide, str):
        try:
            patient_guide = json.loads(patient_guide)
        except (json.JSONDecodeError, TypeError):
            patient_guide = {'items': []}

    return _resp(200, {
        'session_id': session.get('session_id'),
        'patient_name_masked': '김*자',  # mock
        'patient_guide': patient_guide,
        'doctor_additional_notes': doctor_review.get('additional_notes', ''),
    })


# ─────────────────────────────────
# 의료진 확인 항목 조립
# ─────────────────────────────────
# 사전 정의된 슬롯별 review_template (간이판 — 실제는 slot_cards.json 참조)
SLOT_REVIEW_TEMPLATES = {
    'throat_irritation': [
        '인후 통증 정도 평가',
        '발열 동반 여부 확인',
        '음식 삼킴 곤란 여부',
    ],
    'nasal_obstruction': [
        '코막힘 양측/일측 확인',
        '콧물 색깔 및 점도',
        '두통 동반 여부',
    ],
    'cough': [
        '가래 동반 여부와 색깔',
        '야간 악화 여부',
        '발열 동반 여부',
        '기침 지속 기간',
    ],
    'hemoptysis': [
        '[우선] 객혈 평가 (X-ray·객담 검사 고려)',
        '[우선] 객혈량과 시작 시점 확인',
    ],
    'dyspnea': [
        '운동 시 vs 안정 시 호흡곤란',
        '청진 시 천명음 확인',
    ],
    'fever': [
        '실제 체온 측정',
        '발열 지속 기간',
    ],
}


def _build_review_items(session):
    responses = session.get('responses', {})
    q1 = responses.get('Q1') or {}
    q3 = responses.get('Q3') or {}
    q4 = responses.get('Q4') or {}

    items = []

    # Q1의 매칭된 슬롯에서 review_template 가져오기
    matched_slots = q1.get('matched_slots', [])
    for slot in matched_slots:
        slot_id = slot.get('slot_id')
        if slot_id in SLOT_REVIEW_TEMPLATES:
            items.extend(SLOT_REVIEW_TEMPLATES[slot_id])

    # Q3 새 증상도 추가 (재진의 경우)
    new_symptoms = q3.get('new_symptom_spans', [])
    for span in new_symptoms:
        slot_ref = span.get('slot_ref')
        if slot_ref in SLOT_REVIEW_TEMPLATES:
            items.extend(SLOT_REVIEW_TEMPLATES[slot_ref])

    # Q4 환자 질문도 답변 항목으로
    for q in q4.get('questions', []):
        items.append(f"답변: {q.get('summary', '')}")

    # 중복 제거 (순서 보존)
    seen = set()
    unique_items = []
    for item in items:
        if item not in seen:
            seen.add(item)
            unique_items.append(item)

    return unique_items


# ─────────────────────────────────
# 기록용 문장 조립 (EMR 복사용)
# ─────────────────────────────────
def _build_transfer_text(session, patient):
    visit_type = session.get('visit_type', 'initial')
    responses = session.get('responses', {})
    q1 = responses.get('Q1') or {}
    q2 = responses.get('Q2') or {}
    q3 = responses.get('Q3') or {}

    if visit_type == 'initial':
        # 초진 톤
        slots_text = ', '.join([s.get('name', '') for s in q1.get('matched_slots', [])])
        onset = q2.get('estimated_onset_relative', '')
        meds = q3.get('extracted_medications', [])
        meds_text = ', '.join([m.get('patient_term', '') for m in meds])

        text = f"{patient['age']}세 {patient['gender']} 환자."
        if onset:
            text += f" {onset}부터"
        if slots_text:
            text += f" {slots_text} 호소."
        if meds_text:
            text += f" {meds_text} 복용 중."
    else:
        # 재진 톤
        progress = q1.get('progress_summary', {})
        improved = progress.get('improved', [])
        worsened = progress.get('worsened', [])
        new = progress.get('new', [])

        text = f"재진 환자 ({patient['age']}세 {patient['gender']})."
        if improved:
            text += f" {', '.join(improved)} 호전."
        if worsened:
            text += f" {', '.join(worsened)} 악화."
        if new:
            text += f" {', '.join(new)} 신규 발생."

    return text


# ─────────────────────────────────
# DynamoDB 응답 → Python dict 변환
# ─────────────────────────────────
def _ddb_to_dict(item):
    """간이 DDB 형식 풀기 (재귀)"""
    if isinstance(item, dict):
        if len(item) == 1:
            key = next(iter(item.keys()))
            val = item[key]
            if key == 'S': return val
            if key == 'N': return float(val) if '.' in val else int(val)
            if key == 'BOOL': return val
            if key == 'NULL': return None
            if key == 'M': return {k: _ddb_to_dict(v) for k, v in val.items()}
            if key == 'L': return [_ddb_to_dict(v) for v in val]
        return {k: _ddb_to_dict(v) for k, v in item.items()}
    return item


def _resp(status, body):
    return {
        'statusCode': status,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET,OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
        },
        'body': json.dumps(body, ensure_ascii=False)
    }
