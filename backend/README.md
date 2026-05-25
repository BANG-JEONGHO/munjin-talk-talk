# 문진톡톡 Backend (AWS Lambda)

## 개요

4개의 Python Lambda 함수로 구성. 모두 무상태(stateless)이며 각자 독립 배포 가능.

```
lambdas/
├── transcribe_start/    음성 업로드 presigned URL 발급 + Transcribe 작업 시작
├── extract_spans/       Bedrock(Claude)으로 환자 발화에서 span 추출
├── match_slots/         Bedrock(Titan Embed)으로 표준 슬롯 매칭
└── validate_output/     JSON Schema + 위험 키워드 + 금지 출력 검증
infrastructure/
└── template.yaml        AWS SAM 템플릿 (API Gateway + Lambda 4개 + S3 + DynamoDB)
```

## 처리 흐름

```
[Frontend]
    │ POST /upload-url { session_id, question_id }
    ▼
[transcribe_start]  ←─ Presigned PUT URL 반환
    │
    │ (프론트가 S3에 PUT)
    ▼
[S3 audio bucket]
    │ ObjectCreated 이벤트
    ▼
[transcribe_start.start_transcription_handler]
    │ start_transcription_job (ko-KR + Custom Vocabulary)
    ▼
[Amazon Transcribe]
    │ 결과 JSON을 S3에 저장
    │
[Frontend GET /transcribe-result?jobName=...]
    │
    ▼
[Frontend POST /process { confirmed_text }]
    │
    ▼
[extract_spans] ─► [match_slots] ─► [validate_output] ─► [DynamoDB]
                                                              │
                                                              ▼
                                                       [Frontend GET /onepager/{sessionId}]
                                                       (의사 화면에서 조회)
```

## 환경변수

각 Lambda에 다음 환경변수를 설정:

| 변수명 | 기본값 | 용도 |
|---|---|---|
| `BEDROCK_MODEL_ID` | `anthropic.claude-3-5-haiku-20241022-v1:0` | 빠르고 저렴한 모델 권장 |
| `EMBED_MODEL_ID` | `amazon.titan-embed-text-v2:0` | 한국어 지원 임베딩 |
| `AUDIO_BUCKET` | `munjin-tok-tok-audio-temp` | 음성 임시 저장소 |
| `CUSTOM_VOCAB_NAME` | (선택) | 강원 사투리 Custom Vocabulary 이름 |
| `MATCH_THRESHOLD` | `0.75` | 슬롯 매칭 임계값 |
| `TOP_K` | `3` | 후보 슬롯 최대 개수 |

## 로컬 테스트

각 Lambda는 단독으로 테스트 가능. AWS 자격증명이 설정된 상태에서:

```bash
cd backend/lambdas/extract_spans
python -c "
import json
from handler import lambda_handler
event = {
    'body': json.dumps({
        'session_id': 'test',
        'question_id': 'Q1',
        'confirmed_text': '어제부터 목이 칼칼하고 코가 맥혀요.'
    })
}
print(lambda_handler(event, None))
"
```

## 배포 (AWS SAM)

```bash
cd backend

# AWS SAM CLI 설치 필요: brew install aws-sam-cli (or pip)
sam build
sam deploy --guided    # 첫 배포: 스택명, 리전 등 입력
# 이후부터는 sam deploy (재배포)
```

자세한 배포 단계는 `../docs/DEPLOYMENT.md` 참고.

## IAM 권한

각 Lambda 실행 역할에 필요한 권한:

| Lambda | 필요 권한 |
|---|---|
| `transcribe_start` | `s3:PutObject`, `transcribe:StartTranscriptionJob`, `transcribe:GetTranscriptionJob` |
| `extract_spans` | `bedrock:InvokeModel` |
| `match_slots` | `bedrock:InvokeModel` |
| `validate_output` | `dynamodb:PutItem` (최종 저장 시) |

SAM 템플릿에 모두 정의되어 있음.

## 비용 추정 (MVP 시연 기준)

음성 1회 60초 기준, 1회 문진 = 4문항:

| 서비스 | 단가 | 1회 비용 |
|---|---|---|
| Transcribe ko-KR | $0.024/min | $0.096 (4회 × 60초) |
| Bedrock Claude Haiku | ~$0.001/문진 | $0.001 |
| Bedrock Titan Embed | ~$0.0001/요청 | $0.0003 |
| Lambda 실행 | 무료 한도 | ~$0 |
| S3 + DynamoDB | 무료 한도 | ~$0 |
| **합계** | | **약 $0.10 / 환자 1명** |

학교 사업단 AWS 학생 크레딧 $100으로 약 1,000명까지 시연 가능.
