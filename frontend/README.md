# 문진톡톡 Frontend (React + Vite)

## 실행

```bash
npm install
npm run dev
```

→ `http://localhost:5173`

## 디렉토리 구조

```
src/
├── main.jsx                 # React 진입점
├── App.jsx                  # 라우터 + 모드 스위처
├── components/
│   ├── tablet/              # 태블릿 프레임, 공통 헤더
│   │   ├── TabletFrame.jsx
│   │   └── ScreenHeader.jsx
│   ├── patient/             # 환자 화면 (세로 태블릿)
│   │   ├── PatientFlow.jsx       # 전체 흐름 조율 (상태 머신)
│   │   ├── VisitTypeScreen.jsx   # 초진/재진 선택
│   │   ├── VoiceScreen.jsx       # Q1~Q4 음성 입력 (재사용)
│   │   ├── VerifyScreen.jsx      # 전사 검증
│   │   ├── SafetyAlertScreen.jsx # 위험 증상 분기
│   │   └── DoneScreen.jsx        # 완료 (대기 순번)
│   └── doctor/              # 의사 원페이퍼 (데스크톱)
│       ├── DoctorOnePager.jsx
│       └── DoctorOnePager.css
├── hooks/
│   └── useAudioRecorder.js  # MediaRecorder API 훅
├── services/
│   └── api.js               # AWS Lambda 호출 (현재 mock)
├── config/
│   ├── questions.js         # 초진/재진 4문항 정의
│   └── safetyKeywords.js    # 위험 키워드 + 감지 함수
└── styles/
    ├── tokens.css           # 디자인 토큰 (CSS variables)
    └── global.css           # 전역 스타일
```

## 환경변수

`.env.local` 파일을 만들고 백엔드 API URL을 지정:

```
VITE_API_BASE_URL=https://your-api-id.execute-api.ap-northeast-2.amazonaws.com
```

값이 비어 있으면 mock 응답을 사용 (화면 흐름만 검증 가능).

## 주요 흐름

### 환자 측 (`PatientFlow.jsx`)
상태 머신: `visit_type` → `q_voice` → `q_verify` → ... → `done`. 위험 키워드 감지 시 `safety_alert`로 분기.

```
[VisitTypeScreen] 초진/재진 선택
        ↓ onConfirm(path)
[VoiceScreen]     Q1~Q4 음성 입력 (재사용)
        ↓ onFinish(audioBlob)
        → uploadAudio() → getTranscript()
        → detectSafetyKeyword() — 위험 시 SafetyAlertScreen으로
[VerifyScreen]    전사 결과 확인
        ↓ onConfirm()
[VoiceScreen]     다음 질문 → 반복
        ↓ Q4 완료
[DoneScreen]      대기 순번 표시
```

### 의사 측 (`DoctorOnePager.jsx`)
4카드 + 사이드바 구조. `getOnePager(sessionId)`로 백엔드에서 데이터 조회.

## 시연 시 주의사항

1. **마이크 권한 필요** — Chrome에서 첫 실행 시 마이크 권한을 허용해주세요.
2. **HTTPS 필요** — `getUserMedia`는 localhost 또는 HTTPS에서만 동작. AWS 배포 시 CloudFront로 HTTPS 자동 처리.
3. **태블릿 시연** — 개발자 도구 → Device Toolbar → iPad Mini 세로 모드로 보면 실제 환경과 동일.

## 빌드 및 배포

```bash
npm run build
# → dist/ 폴더에 정적 파일 생성
# 이 dist를 S3 버킷에 업로드 + CloudFront 배포
```

자세한 배포 절차는 `../docs/DEPLOYMENT.md` 참고.
