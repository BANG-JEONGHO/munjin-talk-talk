# v5 변경사항 (v4 회귀 수정)

## 수정된 문제

### 🐛 [Critical] PatientGuideScreen 화면이 보이지 않던 오류
- 원인: v4 수정 시 변수명을 `activeItemIdx` → `playingIdx`로 변경했으나
  JSX 한 곳에서 옛 변수명이 그대로 남아 있어 `ReferenceError: activeItemIdx is not defined` 발생
- 수정: `<article className={`pg-card ${activeItemIdx === idx ? ...}`}>` → `playingIdx === idx`

### 🐛 [Critical] VisitTypeScreen 디자인 망가짐
- 원인: v4에서 새 CSS 클래스(`patient-info-card`, `visit-options`, `visit-option-card` 등)를
  사용했으나 해당 클래스의 CSS가 정의되지 않아 카드 UI가 사라짐
- 수정: v3 원본 디자인(vt-patient, vt-btn 등) 그대로 복구
- v4에서 사용자가 요청한 변경사항은 다음 방식으로 재반영:
  - 실시간 시계 (useLiveClock) → 헤더 subtitle에 반영
  - "선택하신 내용에 따라..." 안내문 → vt-help div 제거
  - "오늘 진료가 처음이신가요?" 글자 키움 → vt-question-large 클래스만 추가
  - 직원 도움 버튼 폭 → staff-button-wide 클래스 추가
  - 직원 도움 클릭 → onStaffCall 핸들러 연결

### 🐛 VoiceScreen 마이크와 이펙트가 footer에 가려짐
- 원인: v4에서 voice-question을 32px로 너무 키워 콘텐츠가 아래로 밀려 mic가 footer 영역에 가려짐
- 수정: 적정 크기로 조정
  - voice-question: 32px → 26px
  - voice-sub: 17px → 14px
  - voice-example: 15px → 13px
  - voice-body padding-top: 18px → 10px
  - voice-mic-wrap min-height: 180px 명시로 항상 마이크 영역 보존

## 변경 없음 (사용자 확인)
- 의사 원페이퍼 (초진·재진): 더 이상 수정 불필요
- Verify, Done, SafetyAlert: 큰 글자 만족
- 환자 안내문(PatientGuide): 오류만 수정, 나머지 디자인 유지

## v4 → v5 파일 변경
| 파일 | 변경 |
|---|---|
| frontend/src/components/patient/VisitTypeScreen.jsx | 재작성 (v3 디자인 복구) |
| frontend/src/components/patient/PatientGuideScreen.jsx | 1줄 수정 (activeItemIdx → playingIdx) |
| frontend/src/styles/global.css | VoiceScreen 영역 크기 조정 + VisitTypeScreen 글자 클래스 추가 |
