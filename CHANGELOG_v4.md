# v4 변경사항 (UI 수정 반영)

## 환자 화면 (태블릿)

### VisitTypeScreen (시작 화면)
- 헤더 시각이 실시간으로 표시되도록 useLiveClock 훅 추가 (30초마다 갱신)
- "오늘 진료가 처음이신가요?" 메인 글자를 크게 (visit-type-question-large)
- "선택하신 내용에 따라 질문이 달라져요..." 안내문 제거
- "직원 도움" 버튼이 줄바꿈 없이 한 줄로 표시되도록 폭 확장 (staff-button-wide)
- 직원 도움 버튼 클릭 시 StaffCallScreen으로 전환

### StaffCallScreen (신규)
- 직원 호출 후 표시되는 안내 화면
- 알림 펄스 애니메이션 + 경과 시간 카운터
- "직원에게 알림이 갔어요! 잠시만 자리에서 기다려 주세요" 메시지
- 모든 문진 단계에서 "직원 도움" 클릭 시 이 화면으로 라우팅

### VoiceScreen (Q1~Q4)
- 화면 진입 시 0.3초 딜레이 후 자동 녹음 시작
- 메인 글자 + 설명 + 예시 위치 확대 (CSS 클래스 강제 override)
- 직원 도움 버튼에 onStaffCall 핸들러 연결

### VerifyScreen (확인 화면)
- "최종 전사 문장" 라벨 제거 (제목 "제가 이렇게 들었어요"와 통합)
- 초록 chips 박스 3종 (문장 구조 확인 / 원문 보존 / 위험 표현 없음) 전부 제거
- 전사 결과 글자 크기 확대 (transcript-text-large)
- "다시 말할게요" 클릭 시 VoiceScreen 복귀 + VoiceScreen이 자동 녹음 재시작
- "확정한 문장만 의사에게 전달돼요" 푸터 텍스트 제거

### DoneScreen (문진 완료)
- 모든 글자 크기 확대
- 대기 순번을 useQueueNumber 훅으로 실제 작동 (sessionStorage 기반, 같은 날 누적)
- 체크 아이콘 96x96으로 확대

### SafetyAlertScreen (위험 분기)
- 글자 크기 전반적으로 확대
- 긴 안내문 축약: "걱정 마세요. 자주 있는 일이고... 직원이 옆에 오면..."
  → "걱정 마세요. 자주 있는 일입니다. 정확한 확인을 위해 잠시 멈춘 거예요."
- 디자인(amber 톤) 유지

### PatientFlow (전체 흐름)
- STAFF_CALL 단계 추가
- prevStep 추적으로 직원 도움 복귀 시 원래 화면으로 복귀
- forceFlagAtQ prop 추가: 시연 메뉴에서 특정 Q에서 위험 분기 강제 트리거
- initialVisitType prop 추가: 시연 메뉴에서 초진/재진 바로 진입 가능

### PatientGuideScreen (환자 안내문)
- "다시 들려주기" → "말로 재생하기"로 변경
- 토글 동작: 같은 항목 다시 누르면 멈춤, 다른 항목 누르면 그쪽으로 전환
- 재생 중 버튼은 주황색 + pulse 애니메이션
- 컴포넌트 언마운트 시 speechSynthesis.cancel() 호출

## 앱 전역

### App.jsx
- 우측 상단에 시연용 DemoMenu 추가
- 4가지 시나리오: 처음부터 / 초진 / 재진 / 재진+객혈 분기
- PatientFlowWithDemoMenu 래퍼로 시나리오 변경 시 PatientFlow 강제 리마운트

### services/api.js
- mock-flag-trigger-{Q1~Q4} job 처리 추가
- 시연 메뉴에서 위험 발화 강제 트리거 시 객혈 mock 응답
- 재진 일반 mock에서 Q3 객혈 발화 제거 (별도 강제 트리거 시에만 발생)

## 의사 PC 화면

### DoctorOnePager
- "진단명 추천 없음" / "검증 완료" chips 제거
- 의료진 확인 항목 박스 실제 체크 작동 (toggleCheck + checked state)
- 체크 시 파란 테두리 + 체크 아이콘 + 텍스트 취소선
- 체크 박스 전체 영역 클릭 가능 (cursor: pointer + UX)
- [우선] 항목은 주황 테마로 자동 구분
- 재진의 변화 추적 카드를 "오늘 말한 불편함" 디자인으로 통일
  (EMR 미연동이므로 환자가 새로 말한 증상만 표시)
- _normalize 함수에서 symptom_card 타입 무관하게 symptomSlots로 통일

### DoctorAgendaPanel
- "Phase B" 배지 제거
- "답변을 입력하면 LLM이 어르신 친화 문장으로..." 긴 설명 제거
- 환자 발화 원문 카드 디자인 고도화 (dap-full-quote-v4)
  - 그라데이션 배경 + 시계 아이콘
  - 본문/메타 정보 시각 분리
  - 점선 테두리로 인용 강조

## CSS 추가
- global.css: +458 줄 (v4 환자 화면 + 시연 메뉴)
- DoctorOnePager.css: +110 줄 (체크박스 작동 + alert 애니메이션)
- DoctorAgendaPanel.css: +52 줄 (환자 발화 원문 고도화)
- PatientGuideScreen.css: +18 줄 (TTS 재생 상태)
