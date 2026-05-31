# 문진톡톡 MVP 실행 및 배포

문진톡톡은 고령 환자가 태블릿에서 음성으로 문진을 진행하고, 의료진이 원페이퍼로 핵심 내용을 확인한 뒤 환자 안내문까지 생성하는 병원 문진 MVP입니다.

이 문서는 현재 구현된 MVP를 로컬에서 실행하고 AWS에 배포하기 위한 개발자용 문서입니다.

## 저장소 구성

```text
munjin-talk-talk-mvp/
├── frontend/            # React + Vite 웹 앱
├── backend/
│   └── serverless/      # AWS Lambda/API Gateway 백엔드
├── docs/                # 배포 및 구조 문서
├── .gitignore
└── README.md
```

현재 저장소에는 배포와 시연에 필요한 MVP 코드만 남겼습니다. 로컬 IR 실험 데이터, 100명 테스트셋, 평가 산출물, 캐시, 빌드 결과물은 포함하지 않습니다.

## 구현 기능

- 직원 접수: 환자 확인, 초진/재진 선택, 문진 세션 생성
- 환자 태블릿: 음성 입력, STT 결과 확인, 위험 표현 감지 시 직원 호출
- 직원 대리 입력: 중단된 문진을 직원이 직접 입력하고 동일한 백엔드 파이프라인으로 저장
- 의사 대기열: 실제 접수 순번 기반 대기 환자 확인
- 원페이퍼: 증상, 문진 맥락, 환자 질문, 의료진 확인 항목 표시
- 의료진 답변: 질문별 답변과 환자 안내 강조사항 입력
- 환자 안내문: 답변은 쉬운 표현으로 변환하고, 의사 강조사항은 원문 그대로 표시

## 기술 구성

Frontend:

- React
- Vite
- Web Audio API 기반 녹음

Backend:

- API Gateway HTTP API
- AWS Lambda Python 3.12
- DynamoDB
- S3 presigned upload
- Amazon Transcribe
- Amazon Bedrock Nova Pro/Lite

## 프론트엔드 실행

Node.js `20.19+` 또는 `22.12+`가 필요합니다.

```powershell
cd frontend
npm install
Copy-Item .env.example .env.local
```

`frontend/.env.local`에 배포된 API Gateway 주소를 입력합니다.

```text
VITE_API_BASE_URL=https://<api-id>.execute-api.ap-northeast-2.amazonaws.com
```

개발 서버 실행:

```powershell
npm run dev -- --host 127.0.0.1 --port 5173
```

주요 화면:

```text
/staff                 직원 접수
/patient/{sessionId}   환자 태블릿
/doctor/queue          의사 대기열
/doctor/{sessionId}    원페이퍼
/guide/{sessionId}     환자 안내문
```

## 백엔드 배포

백엔드는 AWS SAM 기반 서버리스 앱입니다.

```powershell
cd backend/serverless
sam build
sam deploy --guided
```

자세한 백엔드 설정과 필요한 AWS 리소스는 [../backend/serverless/README.md](../backend/serverless/README.md)를 참고하세요.

## 프론트엔드 배포

```powershell
cd frontend
npm install
npm run build
```

생성된 `frontend/dist` 내부 파일을 AWS Amplify Hosting에 배포합니다. 태블릿 마이크 권한 때문에 실제 배포 URL은 HTTPS여야 합니다.

자세한 배포 순서는 [DEPLOYMENT.md](DEPLOYMENT.md)를 참고하세요.

## MVP 범위

현재 MVP는 아래 흐름을 끝까지 검증하는 데 집중합니다.

```text
직원 접수 → 환자 태블릿 음성 문진 → Bedrock 기반 구조화 → 의사 원페이퍼 → 환자 안내문
```

로그인, 병원 EMR 연동, 보호자 공유 URL, 운영 모니터링은 후속 확장 범위입니다.

## 보안 메모

현재 MVP에는 로그인과 역할별 권한 분리가 없습니다. 외부 공개 테스트 전에는 직원/의사 화면을 Cognito, Amplify 접근 제한, 병원 내부망 또는 VPN으로 보호해야 합니다.
