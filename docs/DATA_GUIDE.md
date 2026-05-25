# 데이터 가이드 (v2)

`data/` 디렉토리는 시스템 동작에 필요한 정적 데이터 파일을 포함합니다. 모두 S3 Knowledge Pack으로 배포되거나 Lambda 디렉토리에 동봉됩니다.

## 1. slot_cards.json — 증상 슬롯 시스템

호흡기 87개 증상 슬롯 + 63개 호흡기 질병 메타데이터.

### 슬롯 카드 구조
```json
{
  "slot_id": "cough",
  "canonical_name": "기침",
  "definition": "기관지·인후 자극에 의해 발생하는 반사적 호기",
  "positive_examples": ["기침이 나요", "콜록콜록", "기침이 멈추질 않아요", ...],
  "ambiguous_examples": ["목이 간질간질해요"],
  "negative_examples": ["기침은 없어요"],
  "review_template": ["가래 동반 여부", "야간 악화 여부", ...],
  "review_priority_when": {"with_hemoptysis": "[우선] 객혈 동반..."},
  "risk_level": "normal",
  "related_diseases": ["기관지염", "감기", "폐렴", ...]
}
```

### 사용처
- match_slots Lambda: positive_examples를 임베딩하여 매칭 기준 생성
- patient_guide Lambda: review_template에서 의료진 확인 항목 자동 조립
- validate_output Lambda: risk_level 참조

### 추가/수정 방법
1. 새 슬롯 추가 시 `slot_id`는 영문 snake_case
2. `positive_examples`는 환자 발화 표현 5개 이상
3. `review_template`은 의료진 검수 필수
4. 추가 후 Lambda 재배포 (콜드 스타트 시 임베딩 재계산)

---

## 2. safety_keywords.json — 위험 키워드 사전

6 카테고리: hemoptysis(객혈), severe_dyspnea(심한 호흡곤란), consciousness_change(의식 변화), severe_chest_pain(심한 흉통), high_fever(고열), anaphylaxis_signs(아나필락시스).

### 구조
```json
{
  "hemoptysis": {
    "label": "객혈 의증",
    "severity": "high",
    "action": "safety_alert",
    "patterns": ["피가 섞", "피가 살짝", "각혈", ...]
  }
}
```

### action 값
- `safety_alert`: 환자 흐름 즉시 중단, SafetyAlertScreen 분기, 직원 호출
- `review_priority`: 일반 흐름 진행, 의사 원페이퍼 amber 배지

### False positive 방지
Validator Lambda에서 컨텍스트 검사 추가. 예: "피곤"·"피로"는 "피" 패턴 매칭에서 제외.

---

## 3. forbidden_outputs.json — 금지 출력 패턴

AI 출력에서 차단해야 할 패턴. 4 카테고리:
- diagnosis: 진단명 단정 ("(.*)병입니다")
- prescription: 처방 권유 ("처방.*권장")
- treatment_recommendation: 치료 권유 ("수술.*권장")
- emergency_routing: 응급실 권유 ("응급실.*가세요")

### 적용 위치
- validate_output Lambda: matched_slots와 structured 데이터에 적용
- doctor_response Lambda (Validator 2차): patient_guide 생성 결과에 적용

---

## 4. patient_guide_template.json — Phase B LLM 프롬프트

의사 답변을 어르신 친화적 문장으로 변환할 때 사용하는 프롬프트 모음.

### 카테고리별 프롬프트
- default: 범용 변환
- drug_drug_interaction: 약물 상호작용 답변 (약 이름 보존)
- food_drug_interaction: 음식·건강식품 답변
- treatment_duration: 복약 기간 답변
- prognosis: 회복 시점 답변
- prognosis_concern: 우려 답변 (안심 + 가이드)

### 변환 규칙
- 한 문장 30자 이내
- 의학 용어 → 일상 표현
- 새 의학 정보 추가 금지 (Validator 2차 차단)
- 진단명·처방 권유 금지

---

## 데이터 구분: 문제 인식용 vs 서비스 구현용

### 문제 인식용 (발표·기획서)
R01~R26 통계 자료 → 별도 `근거자료_정리.docx` 참조. 본 디렉토리에는 포함되지 않음.

### 서비스 구현용 (실 코드)
- slot_cards.json (의료 콘텐츠 — AMC 질환백과 기반)
- safety_keywords.json (자체 정의)
- forbidden_outputs.json (자체 정의)
- patient_guide_template.json (자체 정의)

KCD-9 호흡기 코드(HIRA 상병마스터) 매핑은 slot_cards.json의 related_diseases에 향후 추가 예정.
