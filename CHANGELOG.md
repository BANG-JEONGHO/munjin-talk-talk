# Changelog

## v3.0 — 2026.05.20 (의료 인력 0명 환경 최적화)

### Tool Use 도입 — JSON 안정성
- **extract_spans Lambda 재작성**: Bedrock Converse API + toolChoice로 JSON Schema 강제. 6개 question_type별 도구 정의 (extract_chief_complaint, extract_progress, extract_medications, extract_new_symptoms, categorize_patient_questions × 2)
- **doctor_response Lambda 재작성**: TOOL_PATIENT_GUIDE로 어르신 친화 변환 안정화
- **enum·required·maxLength** 등 모든 제약을 모델 단에서 강제. JSON 파싱 에러 사실상 0

### Q4 누락 방지 4중 묘수
- 묘수 ①: Tool Use 스키마에 `uncategorized_remnant` 필드 강제
- 묘수 ②: 2단계 처리 가능 구조 (선택)
- 묘수 ③: Q2 adherence 패턴이 side_effect·refusal 별도 흡수 (`extract_spans` Lambda)
- 묘수 ④: 의사 화면에 환자 발화 원문 카드 상시 표시 (`DoctorAgendaPanel`)

### Validator 2차 강화 (doctor_response Lambda)
- 새 진단·처방 권유 단어 차단 (8개 패턴)
- 새 약 이름 추가 차단 (DRUG_PATTERN regex)
- 새 수치 추가 차단 (NUMERIC_PATTERN regex)
- 새 질병명 추가 차단 (DISEASE_PATTERN regex)
- 차단 시 의사 답변 원문으로 자동 폴백

### UI 개선안 2 적용 (좌측 visit_type 분기 / 우측 공통)
- **신규**: `DoctorAgendaPanel.jsx` — 우측 통합 패널 (질문 + 답변 인라인 + 원문 상시 표시 + 잔여 텍스트 경고)
- **재작성**: `DoctorOnePager.jsx` — 좌측 3카드 + sidePanel prop 받기
- **재작성**: `DoctorView.jsx` — sidePanel을 DoctorAgendaPanel로 주입
- **삭제**: `DoctorResponseInput.jsx` (DoctorAgendaPanel로 통합)
- 상단 가로 띠: 위험 amber 배지 + 환자 정보
- 1280px 이상에서 좌우 분할, 그 미만에서는 세로 스택

### 빌드 자동화 4개 스크립트 (`scripts/builders/`)
- `build_slot_cards.py` — 호흡기 87 슬롯 정의·예시 자동 생성 (약 $0.30)
- `build_review_templates.py` — 슬롯별 의료진 확인 항목 자동 생성 (약 $0.50)
- `build_safety_keywords.py` — 위험 키워드 6 카테고리 + false_positive_excludes (약 $0.05)
- `build_forbidden_outputs.py` — 금지 출력 4 카테고리 (약 $0.05)
- `build_all.py` — 통합 러너
- `README.md` — 사용법·트러블슈팅

모든 스크립트는 Tool Use 기반. 총 비용 약 $1, 시간 약 1.2시간. 의료 인력 검수 불필요.

---

## v2.0 — 2026.05.20 (이전)
- Phase B 양면 흐름 (doctor_response + patient_guide Lambda)
- 87 슬롯 + 63 호흡기 질병
- 초진/재진 분기
- 위험 키워드 분기

## v1.0 — 초기 버전
- 환자 음성 문진 4문항
- 슬롯 매칭 5개 (목 불편감, 코막힘, 기침, 가래, 발열)
- 의사 원페이퍼 (4카드)
