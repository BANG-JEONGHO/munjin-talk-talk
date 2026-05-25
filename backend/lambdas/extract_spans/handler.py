"""
extract_spans Lambda (v3 — Tool Use 적용)
─────────────────────────────────────────
POST /extract

Bedrock Converse API + Tool Use로 JSON Schema를 모델 단에서 강제.
프롬프트 의존 방식 대비 시연 도중 JSON 파싱 실패·필수 필드 누락
사고가 사실상 0에 수렴.

하이브리드 LLM 전략 (옵션 C):
- Q1 chief_complaint / progress  → Claude Tool Use (extract_spans)
- Q2 onset / adherence            → 규칙 기반 (LLM 0회)
- Q3 current_medications          → Claude Tool Use (extract_medications)
- Q3 new_symptoms (재진)          → Claude Tool Use (extract_new_symptoms)
- Q4 patient_questions            → Claude Tool Use (categorize_questions)
- Q4 unresolved_questions         → Claude Tool Use (categorize_questions)
"""

import os
import re
import json
import boto3

bedrock = boto3.client('bedrock-runtime', region_name=os.environ.get('AWS_REGION', 'ap-northeast-2'))
CLAUDE_MODEL = os.environ.get('CLAUDE_MODEL_ID', 'anthropic.claude-3-5-haiku-20241022-v1:0')


# ────────────────────────────────────────────────
# Tool 정의 (JSON Schema 강제)
# ────────────────────────────────────────────────

TOOL_CHIEF_COMPLAINT = {
    'toolSpec': {
        'name': 'extract_chief_complaint',
        'description': '환자 발화에서 증상·시점·기간·맥락 span을 추출. source_quote는 원문에 정확히 존재하는 부분 문자열이어야 함.',
        'inputSchema': {
            'json': {
                'type': 'object',
                'properties': {
                    'spans': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'source_quote': {
                                    'type': 'string',
                                    'description': '환자 원문에 정확히 존재하는 부분 문자열'
                                },
                                'type': {
                                    'type': 'string',
                                    'enum': ['symptom', 'onset', 'duration', 'context']
                                }
                            },
                            'required': ['source_quote', 'type']
                        }
                    }
                },
                'required': ['spans']
            }
        }
    }
}

TOOL_PROGRESS = {
    'toolSpec': {
        'name': 'extract_progress',
        'description': '재진 환자의 증상 변화를 추출. 각 span에 변화 유형과 표준 슬롯 ID(slot_ref) 부여.',
        'inputSchema': {
            'json': {
                'type': 'object',
                'properties': {
                    'spans': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'source_quote': {'type': 'string'},
                                'type': {
                                    'type': 'string',
                                    'enum': ['progress_improved', 'progress_unchanged',
                                             'progress_worsened', 'new_symptom']
                                },
                                'slot_ref': {
                                    'type': 'string',
                                    'enum': [
                                        'cough', 'throat_irritation', 'nasal_obstruction',
                                        'rhinorrhea', 'fever', 'sputum', 'dyspnea',
                                        'hemoptysis', 'chest_pain', 'wheezing', 'headache',
                                        'sneezing', 'voice_change', 'sore_throat', 'other'
                                    ]
                                }
                            },
                            'required': ['source_quote', 'type', 'slot_ref']
                        }
                    }
                },
                'required': ['spans']
            }
        }
    }
}

TOOL_MEDICATIONS = {
    'toolSpec': {
        'name': 'extract_medications',
        'description': '환자가 현재 복용 중이라고 언급한 약을 카테고리별로 추출.',
        'inputSchema': {
            'json': {
                'type': 'object',
                'properties': {
                    'extracted_medications': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'category': {
                                    'type': 'string',
                                    'enum': ['antihypertensive', 'diabetes', 'anticoagulant',
                                             'painkiller', 'supplement', 'respiratory', 'other']
                                },
                                'patient_term': {
                                    'type': 'string',
                                    'description': '환자가 사용한 표현 그대로'
                                },
                                'frequency': {
                                    'type': 'string',
                                    'description': '복용 빈도 (\"매일 아침\", \"식후 30분\" 등)'
                                }
                            },
                            'required': ['category', 'patient_term']
                        }
                    },
                    'denied_categories': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': '환자가 명시적으로 부정한 카테고리'
                    }
                },
                'required': ['extracted_medications']
            }
        }
    }
}

TOOL_NEW_SYMPTOMS = {
    'toolSpec': {
        'name': 'extract_new_symptoms',
        'description': '재진 환자가 새로 생긴 증상 또는 악화된 증상을 보고하는 발화에서 추출.',
        'inputSchema': {
            'json': {
                'type': 'object',
                'properties': {
                    'new_symptom_spans': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'source_quote': {'type': 'string'},
                                'type': {
                                    'type': 'string',
                                    'enum': ['new', 'worsening']
                                },
                                'slot_ref': {
                                    'type': 'string',
                                    'enum': [
                                        'cough', 'throat_irritation', 'nasal_obstruction',
                                        'rhinorrhea', 'fever', 'sputum', 'dyspnea',
                                        'hemoptysis', 'chest_pain', 'wheezing', 'headache',
                                        'sneezing', 'voice_change', 'sore_throat', 'other'
                                    ]
                                }
                            },
                            'required': ['source_quote', 'type', 'slot_ref']
                        }
                    }
                },
                'required': ['new_symptom_spans']
            }
        }
    }
}

TOOL_CATEGORIZE_QUESTIONS = {
    'toolSpec': {
        'name': 'categorize_patient_questions',
        'description': """환자 발화에서 의사에게 묻고 싶은 모든 질문을 카테고리별로 분리하고
명사구로 요약. AI 답변 시도 절대 금지 — 정리만 수행.
누락 방지를 위해 uncategorized_remnant 필드에 분류되지 않은 잔여 텍스트를 반드시 기록.""",
        'inputSchema': {
            'json': {
                'type': 'object',
                'properties': {
                    'questions': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'category': {
                                    'type': 'string',
                                    'enum': ['drug_drug_interaction', 'food_drug_interaction',
                                             'treatment_duration', 'prognosis',
                                             'general_health_info', 'prognosis_concern', 'other']
                                },
                                'summary': {
                                    'type': 'string',
                                    'maxLength': 60,
                                    'description': '의사가 30초에 읽을 수 있는 명사구 요약'
                                },
                                'original_quote': {
                                    'type': 'string',
                                    'description': '환자가 실제 말한 부분 (원문)'
                                }
                            },
                            'required': ['category', 'summary', 'original_quote']
                        }
                    },
                    'uncategorized_remnant': {
                        'type': 'string',
                        'description': """카테고리화하지 못한 잔여 텍스트. 없으면 빈 문자열.
의미 있는 내용이 남으면 안 됨. 누락이 의심되면 새 questions 항목을 추가하세요."""
                    }
                },
                'required': ['questions', 'uncategorized_remnant']
            }
        }
    }
}


# ────────────────────────────────────────────────
# 프롬프트 (간결화 — Tool Schema가 형식을 강제하므로)
# ────────────────────────────────────────────────

PROMPTS = {
    'chief_complaint': """다음 환자 발화에서 의미 단위 span을 추출하세요.

환자 발화: "{transcript}"

규칙:
- source_quote는 환자 원문에 정확히 존재하는 부분 문자열이어야 함.
- 의학 용어로 의역하지 말 것 ("칼칼하다"를 "인후 자극"으로 바꾸지 말 것).
- 진단·처방·검사 권유 생성 금지.

extract_chief_complaint 도구를 호출하세요.""",

    'progress': """재진 환자가 지난 진료 이후 증상 변화를 보고한 발화입니다.

환자 발화: "{transcript}"

각 증상에 대해:
- progress_improved: 호전 ("나아졌다", "좋아졌다")
- progress_unchanged: 유지 ("그대로", "비슷")
- progress_worsened: 악화 ("더 심해", "나빠졌다")
- new_symptom: 신규 발생 (지난 진료에 없던)

slot_ref에는 변화하는 증상의 표준 슬롯 ID 부여.

extract_progress 도구를 호출하세요.""",

    'current_medications': """환자가 현재 복용 중인 약을 보고한 발화입니다.

환자 발화: "{transcript}"

명시적으로 부정한 카테고리(예: "다른 약은 안 먹어요")도 denied_categories에 기록.

extract_medications 도구를 호출하세요.""",

    'new_symptoms': """재진 환자가 새로 생긴 증상이나 변화를 보고한 발화입니다.

환자 발화: "{transcript}"

- new: 지난 진료에 없던 신규 증상
- worsening: 기존 증상 악화

extract_new_symptoms 도구를 호출하세요.""",

    'patient_questions': """환자가 의사에게 묻고 싶은 질문을 말한 발화입니다.

환자 발화: "{transcript}"

작업:
1. 환자가 한 질문을 카테고리별로 모두 분리 (한 발화에 여러 질문 섞일 수 있음).
2. 각 질문을 명사구로 요약.
3. AI 답변 시도 절대 금지. 정리만 수행.
4. 분류 후 남은 잔여 텍스트는 uncategorized_remnant에 그대로 기록.
   의미 있는 내용이 잔여에 남으면 누락된 것이므로 다시 분류해서 questions에 추가하세요.

categorize_patient_questions 도구를 호출하세요.""",

    'unresolved_questions': """재진 환자가 지난번에 못 여쭤본 질문을 말한 발화입니다.

환자 발화: "{transcript}"

patient_questions와 동일한 방식으로 분류하세요.
누락 방지: uncategorized_remnant 필드 반드시 채우기.

categorize_patient_questions 도구를 호출하세요.""",
}


# Tool 매핑
TOOL_FOR_TYPE = {
    'chief_complaint':       TOOL_CHIEF_COMPLAINT,
    'progress':              TOOL_PROGRESS,
    'current_medications':   TOOL_MEDICATIONS,
    'new_symptoms':          TOOL_NEW_SYMPTOMS,
    'patient_questions':     TOOL_CATEGORIZE_QUESTIONS,
    'unresolved_questions':  TOOL_CATEGORIZE_QUESTIONS,
}


# ────────────────────────────────────────────────
# Tool Use 호출 (Converse API)
# ────────────────────────────────────────────────

def call_claude_with_tool(prompt, tool_spec):
    """Bedrock Converse API + toolChoice로 JSON Schema 강제 호출"""
    tool_name = tool_spec['toolSpec']['name']

    response = bedrock.converse(
        modelId=CLAUDE_MODEL,
        messages=[{
            'role': 'user',
            'content': [{'text': prompt}]
        }],
        toolConfig={
            'tools': [tool_spec],
            'toolChoice': {'tool': {'name': tool_name}}  # 무조건 이 도구만 호출
        },
        inferenceConfig={
            'temperature': 0.1,
            'maxTokens': 1024
        }
    )

    # 응답에서 toolUse 블록 추출
    content = response['output']['message']['content']
    for block in content:
        if 'toolUse' in block:
            return block['toolUse']['input']

    # 도구 호출 실패 시 빈 결과
    return {}


# ────────────────────────────────────────────────
# Q2: 규칙 기반 처리 (LLM 호출 없음)
# ────────────────────────────────────────────────

ONSET_PATTERNS = [
    (r'(\d+)일\s*전',                lambda m: f"{m.group(1)}일 전"),
    (r'어제부터|어젯밤부터',          lambda _: "1일 전"),
    (r'그저께부터|그저께\s*저녁부터', lambda _: "2일 전"),
    (r'오늘\s*아침|오늘부터',         lambda _: "당일"),
    (r'지난주',                        lambda _: "약 1주 전"),
    (r'이번\s*주',                     lambda _: "이번 주"),
    (r'(\d+)주\s*전',                 lambda m: f"{m.group(1)}주 전"),
    (r'(\d+)개월\s*전',               lambda m: f"{m.group(1)}개월 전"),
    (r'한\s*달\s*전',                 lambda _: "약 1개월 전"),
    (r'보름\s*전',                     lambda _: "약 15일 전"),
]

CONTEXT_PATTERNS = {
    r'추웠|추워|찬바람|한기':     '한기 노출',
    r'비를\s*맞|젖었':            '강우 노출',
    r'감기\s*걸린\s*사람|확진자':  '전염원 접촉',
    r'먼지|공사장|매연':           '공기 자극원 노출',
}

ADHERENCE_PATTERNS = {
    r'잘\s*먹었|잘\s*드시|꾸준히':                      ('adherence_positive', '잘 복용'),
    r'깜빡|잊었|빠뜨렸|놓쳤':                            ('adherence_gap', '간헐적 누락'),
    r'아침에\s*못|점심에\s*못|저녁에\s*못':               ('adherence_pattern', '시간대 누락'),
    r'부작용|속이\s*쓰리|어지러|메스꺼|두드러기':         ('side_effect', '부작용 가능성'),
    r'안\s*먹었|먹기\s*싫|거부|중단':                    ('adherence_refusal', '복약 거부'),
}


def process_onset(transcript):
    spans = []
    estimated = None
    context_hints = []

    for pattern, formatter in ONSET_PATTERNS:
        m = re.search(pattern, transcript)
        if m:
            spans.append({'source_quote': m.group(0), 'type': 'onset'})
            estimated = formatter(m)
            break

    for pattern, hint in CONTEXT_PATTERNS.items():
        m = re.search(pattern, transcript)
        if m:
            spans.append({'source_quote': m.group(0), 'type': 'context'})
            context_hints.append(hint)

    return {
        'spans': spans,
        'structured': {
            'estimated_onset_relative': estimated or '불명확 (의사 직접 확인 권장)',
            'context_hints': context_hints,
            'fallback': estimated is None
        }
    }


def process_adherence(transcript):
    spans = []
    detected_labels = []

    for pattern, (span_type, label) in ADHERENCE_PATTERNS.items():
        m = re.search(pattern, transcript)
        if m:
            spans.append({'source_quote': m.group(0), 'type': span_type})
            detected_labels.append(label)

    types_present = set(s['type'] for s in spans)
    if 'side_effect' in types_present:
        level = 'side_effect_reported'
    elif 'adherence_refusal' in types_present:
        level = 'low_adherence'
    elif types_present & {'adherence_gap', 'adherence_pattern'}:
        level = 'mostly_adherent_with_gaps'
    elif 'adherence_positive' in types_present:
        level = 'good_adherence'
    else:
        level = 'unclear'

    return {
        'spans': spans,
        'structured': {
            'adherence_level': level,
            'side_effects_reported': 'side_effect' in types_present,
            'detected_labels': detected_labels
        }
    }


# ────────────────────────────────────────────────
# 원문 검증 (Tool Use 후에도 안전망)
# ────────────────────────────────────────────────

def validate_spans_in_original(spans, transcript):
    """source_quote가 원문에 substring으로 존재하는지"""
    valid = []
    for span in spans:
        sq = span.get('source_quote', '')
        if sq and sq in transcript:
            valid.append(span)
        else:
            print(f"[REJECT] source_quote not in original: {sq!r}")
    return valid


# ────────────────────────────────────────────────
# 메인 핸들러
# ────────────────────────────────────────────────

def handler(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
    except json.JSONDecodeError:
        return _resp(400, {'error': 'invalid_json'})

    session_id    = body.get('session_id')
    question_id   = body.get('question_id')
    question_type = body.get('question_type')
    visit_type    = body.get('visit_type', 'initial')
    transcript    = (body.get('transcript') or '').strip()

    if not all([session_id, question_id, question_type, transcript]):
        return _resp(400, {'error': 'missing_required_fields'})

    # Q2: 규칙 기반 (LLM 호출 0회)
    if question_type == 'onset':
        return _resp(200, {**process_onset(transcript), 'transcript': transcript, 'method': 'rule_based'})

    if question_type == 'adherence':
        return _resp(200, {**process_adherence(transcript), 'transcript': transcript, 'method': 'rule_based'})

    # Q1/Q3/Q4: Tool Use 기반 Claude 호출
    if question_type not in PROMPTS:
        return _resp(400, {'error': f'unknown_question_type: {question_type}'})

    prompt = PROMPTS[question_type].format(transcript=transcript)
    tool_spec = TOOL_FOR_TYPE[question_type]

    try:
        result = call_claude_with_tool(prompt, tool_spec)
    except Exception as e:
        print(f"[ERROR] Claude Tool Use 실패: {e}")
        return _resp(500, {'error': 'claude_failed', 'detail': str(e)})

    # source_quote 원문 검증 (Tool Use 후에도 안전망 유지)
    if 'spans' in result:
        result['spans'] = validate_spans_in_original(result['spans'], transcript)

    if 'new_symptom_spans' in result:
        result['new_symptom_spans'] = validate_spans_in_original(result['new_symptom_spans'], transcript)

    if 'questions' in result:
        result['questions'] = [
            q for q in result['questions']
            if q.get('original_quote', '') in transcript
        ]

    # 응답 구조 정규화
    spans = result.get('spans') or result.get('new_symptom_spans') or []
    structured = {k: v for k, v in result.items()
                  if k not in ('spans', 'new_symptom_spans')}

    return _resp(200, {
        'spans': spans,
        'structured': structured,
        'transcript': transcript,
        'method': 'claude_tool_use'
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
