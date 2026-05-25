# 배포 가이드

## 사전 준비

```bash
# AWS CLI 설치 및 자격증명 설정
aws --version
aws configure   # Access Key, Secret Key, region (ap-northeast-2 권장)

# SAM CLI 설치
brew install aws-sam-cli           # macOS
# or
pip install aws-sam-cli            # 그 외

# Node.js
node --version  # v18+ 권장
```

Bedrock 모델 액세스 활성화: AWS 콘솔 → **Amazon Bedrock** → **Model access** → 다음 모델 신청:
- `anthropic.claude-3-5-haiku-20241022-v1:0`
- `amazon.titan-embed-text-v2:0`

(승인까지 보통 5-10분. 학내 사업단 계정에서 거부될 수 있으니 미리 신청.)

## 1. 백엔드 배포

```bash
cd backend

# 첫 배포 (대화형)
sam build
sam deploy --guided

# 입력 예시:
#   Stack Name: munjin-tok-tok
#   Region: ap-northeast-2
#   Confirm changes: y
#   Allow SAM CLI IAM role creation: y
#   Save arguments to samconfig.toml: y

# 이후 재배포:
sam deploy
```

배포 완료되면 출력에서 `ApiEndpoint` 확인:
```
Outputs:
  ApiEndpoint: https://xxxxx.execute-api.ap-northeast-2.amazonaws.com/prod
```

이 값을 프론트엔드 `.env.local`에 복사.

## 2. Transcribe Custom Vocabulary 등록 (선택, 권장)

강원 사투리 및 의료 용어를 사전에 등록하면 STT 정확도가 크게 개선됩니다.

```bash
# vocab.txt 생성 (한 줄에 한 단어)
cat > vocab.txt <<EOF
맥혀요
칼칼하다
욱신거리다
쑤시다
어르신
객담
인후염
부비동염
EOF

# S3 업로드
aws s3 cp vocab.txt s3://munjin-tok-tok-audio-temp/vocab.txt

# Vocabulary 생성
aws transcribe create-vocabulary \
  --vocabulary-name munjin-gangwon \
  --language-code ko-KR \
  --vocabulary-file-uri s3://munjin-tok-tok-audio-temp/vocab.txt

# 상태 확인 (READY 될 때까지 대기)
aws transcribe get-vocabulary --vocabulary-name munjin-gangwon
```

상태가 `READY`가 되면 Lambda 환경변수 `CUSTOM_VOCAB_NAME`을 `munjin-gangwon`으로 설정.

```bash
# SAM 재배포 시 파라미터로 전달
sam deploy --parameter-overrides CustomVocabName=munjin-gangwon
```

## 3. 프론트엔드 배포

### 3.1 환경변수 설정

```bash
cd frontend
cp .env.example .env.local
# .env.local 편집:
# VITE_API_BASE_URL=https://xxxxx.execute-api.ap-northeast-2.amazonaws.com/prod
```

### 3.2 빌드

```bash
npm install
npm run build
# → dist/ 폴더 생성
```

### 3.3 S3 + CloudFront 배포

```bash
# 프론트엔드 정적 호스팅용 버킷 생성
BUCKET=munjin-tok-tok-frontend-$(date +%s)
aws s3 mb s3://$BUCKET --region ap-northeast-2

# 정적 웹사이트 호스팅 활성화
aws s3 website s3://$BUCKET --index-document index.html

# 빌드 결과 업로드
aws s3 sync dist/ s3://$BUCKET --delete

# 퍼블릭 액세스 정책 적용
cat > bucket-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": "*",
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::$BUCKET/*"
  }]
}
EOF
aws s3api put-bucket-policy --bucket $BUCKET --policy file://bucket-policy.json

# CloudFront 배포 (HTTPS 자동) - 콘솔에서 더 간편
# Origin: $BUCKET.s3.amazonaws.com
# Default Root Object: index.html
# Viewer Protocol Policy: Redirect HTTP to HTTPS
```

CloudFront 도메인이 발급되면 (`dxxxxx.cloudfront.net`) 거기로 접속.

## 4. 시연 환경 점검

배포 완료 후 다음을 확인:

```bash
# 백엔드 헬스체크
curl https://xxxxx.execute-api.ap-northeast-2.amazonaws.com/prod/upload-url \
  -X POST -H "Content-Type: application/json" \
  -d '{"session_id":"test","question_id":"Q1"}'
# → upload_url 키가 포함된 JSON이 와야 정상

# 프론트엔드
# 브라우저에서 https://dxxxxx.cloudfront.net 접속
# → 태블릿 UI 보이고, 마이크 권한 허용 가능해야 정상
```

## 5. 시연 당일 체크리스트

- [ ] 태블릿 Chrome 또는 Edge 최신 버전 (마이크 권한)
- [ ] 인터넷 연결 안정 확인
- [ ] AWS 학생 크레딧 잔액 확인
- [ ] Bedrock 모델 액세스 활성화 재확인
- [ ] 시연 시나리오: 김*자 어르신, 초진/재진 각 1회씩
- [ ] 백업: 시연 영상 캡처본 1개 미리 준비 (네트워크 장애 대비)

## 트러블슈팅

| 증상 | 원인 | 해결 |
|---|---|---|
| 마이크 권한 거부됨 | HTTP로 접속함 | CloudFront 도메인 (HTTPS) 사용 |
| STT 결과 안 옴 | Transcribe 권한 미부여 | Lambda IAM 정책 확인 |
| Bedrock 호출 실패 | 모델 액세스 미승인 | 콘솔에서 Model access 신청 |
| CORS 에러 | API Gateway CORS 설정 | template.yaml의 Cors 블록 확인 |
| 슬롯 매칭 결과 빈 배열 | 임계값 너무 높음 | `MATCH_THRESHOLD`를 0.6 등으로 낮추기 |

## 비용 관리

```bash
# Bedrock 사용량 확인
aws ce get-cost-and-usage \
  --time-period Start=$(date -v-7d +%Y-%m-%d),End=$(date +%Y-%m-%d) \
  --granularity DAILY \
  --metrics UnblendedCost \
  --filter '{"Dimensions":{"Key":"SERVICE","Values":["Amazon Bedrock"]}}'

# 비용 예산 알림 설정 (콘솔 권장)
# Billing → Budgets → 월 $20 알림 설정
```

## 리소스 정리 (시연 종료 후)

```bash
# 백엔드 삭제
cd backend
sam delete

# 프론트엔드 삭제
aws s3 rm s3://$BUCKET --recursive
aws s3 rb s3://$BUCKET

# CloudFront 배포 비활성화 (콘솔에서 Disable → Delete)

# Custom Vocabulary 삭제
aws transcribe delete-vocabulary --vocabulary-name munjin-gangwon
```
