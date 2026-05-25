# 아키텍처 문서 (v2)

## 4밴드 11서비스 구성

```
┌─ FRONTEND ─────────────────────────────────────────────────┐
│  CloudFront (HTTPS + CDN)  →  S3 Static (React SPA)        │
│  라우팅: / → 환자  /doctor → 의사  /guide → 환자 안내       │
└────────────────────────────────────────────────────────────┘

┌─ API LAYER ────────────────────────────────────────────────┐
│  API Gateway HTTP API  →  Lambda 7개                       │
│  • POST /upload-url       (upload_url)                     │
│  • GET  /transcribe-result (transcribe_start)              │
│  • POST /extract          (extract_spans)                  │
│  • POST /match            (match_slots)                    │
│  • POST /validate         (validate_output)                │
│  • POST /doctor-response  (doctor_response)                │
│  • GET  /onepager/{id}    (patient_guide)                  │
│  • GET  /guide/{id}       (patient_guide)                  │
└────────────────────────────────────────────────────────────┘

┌─ AI PROCESSING ────────────────────────────────────────────┐
│ Phase A (진료 전):                                          │
│  환자 음성 → S3 → Transcribe ko-KR + Custom Vocabulary     │
│  → Bedrock Claude (Span Extract, Q1/Q3/Q4)                  │
│  → Bedrock Titan Embed v2 (Vector Match, Q1만)             │
│  → Validator (4단 검증) → DynamoDB sessions               │
│                                                            │
│ Phase B (진료 후):                                          │
│  의사 답변 입력 → Bedrock Claude (Patient Guide Generator) │
│  → Validator 2차 (의학 정보 추가 차단)                     │
│  → DynamoDB → 환자 안내 화면                               │
└────────────────────────────────────────────────────────────┘

┌─ STORAGE ──────────────────────────────────────────────────┐
│  DynamoDB sessions table (session_id PK)                   │
│    - visit_type, responses, doctor_review, patient_guide   │
│  S3 Audio (sessions/ 1일 TTL)                              │
│  S3 Knowledge Pack (slot_cards.json 등 4파일)              │
└────────────────────────────────────────────────────────────┘
```

## Phase A — 진료 전 (한 질문당 시퀀스)

```
환자 음성 녹음 (MediaRecorder API)
    ↓
POST /upload-url → presigned URL + s3_key
    ↓
브라우저 → S3 PUT (audio Blob)
    ↓
S3 ObjectCreated 이벤트 → transcribe_start Lambda 자동 트리거
    ↓
Amazon Transcribe (ko-KR, Custom Vocabulary 적용)
    ↓
GET /transcribe-result (폴링) → 전사 결과
    ↓
환자 검증 화면 → "맞아요" 클릭
    ↓
POST /extract → Span 추출 (Claude or 규칙 기반)
POST /match → 벡터 매칭 (Titan, Q1만)
POST /validate → 4단 검증 + DDB UpdateItem
    ↓
다음 질문 (Q2~Q4) 또는 DONE
```

## Phase B — 진료 후

```
의사 PC: GET /onepager/{sessionId} → 4카드 원페이퍼 표시
    ↓
의사가 Q4 답변 textarea에 답변 입력
    ↓
POST /doctor-response (answers[])
    ↓ doctor_response Lambda:
       1) DDB에 doctor_review 저장
       2) Claude로 각 답변을 어르신 친화 문장 변환
       3) Validator 2차 (의사 답변에 없는 의학 정보 추가 차단)
       4) DDB에 patient_guide 저장
    ↓
환자 태블릿: GET /guide/{sessionId} → 큰 글자 + TTS + 보호자 공유
```

## 하이브리드 LLM 호출 (옵션 C)

| 질문 | 초진 type | 재진 type | LLM 호출 |
|---|---|---|---|
| Q1 | chief_complaint | progress | Claude Extract + Titan Match × N |
| Q2 | onset | adherence | **규칙 기반 (LLM 없음)** |
| Q3 | current_medications | new_symptoms | Claude Extract만 |
| Q4 | patient_questions | unresolved_questions | Claude Categorizer × 1 |
| Phase B | patient_guide | patient_guide | Claude × 답변 수 |

환자 1명당 Claude 약 4~5회 + Titan 약 3~5회 = 총 7~10회 LLM 호출. 비용 약 $0.006/환자.

## 위험 키워드 분기

`safety_keywords.json`의 6개 카테고리 (hemoptysis, severe_dyspnea, consciousness_change, severe_chest_pain, high_fever, anaphylaxis_signs) 패턴 매칭 시:

- severity=high + action=safety_alert → 일반 흐름 중단, SafetyAlertScreen 분기, 직원 호출
- severity=medium + action=review_priority → 일반 흐름 진행, 의사 원페이퍼에 amber 배지

False positive 방지를 위해 컨텍스트 검사 추가 (예: "피곤"은 "피" 패턴 매칭 제외).

## 데이터 흐름

자세한 시퀀스는 `/mnt/user-data/outputs/문진톡톡_데이터흐름_시퀀스.svg` 참조.

각 단계에서 JSON 객체가 누적 갱신되어 DynamoDB sessions 테이블에 최종 저장. 스키마 v1.0은 `data/slot_cards.json`의 `_meta` 필드 참조.
