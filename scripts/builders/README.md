# 빌드 자동화 스크립트

의료 인력 없이도 작동하는 의료 도메인 데이터 자동 생성 파이프라인.

## 개요

문진톡톡은 87개 호흡기 슬롯 카드, 위험 키워드 사전, 금지 출력 패턴 등 의료 도메인 데이터가 필요한데, 팀 내 의료 인력이 없는 제약을 극복하기 위해 모든 데이터를 Claude Sonnet에 위임해 자동 생성합니다.

**총 비용: 약 $1 · 총 시간: 약 1.2시간**

## 사전 준비

```bash
# AWS 자격증명 설정 (학생 크레딧 계정)
export AWS_ACCESS_KEY_ID=AKIA...
export AWS_SECRET_ACCESS_KEY=...
export AWS_REGION=ap-northeast-2

# Bedrock 모델 액세스 활성화 (콘솔에서)
# - anthropic.claude-3-5-sonnet-20241022-v2:0
# - anthropic.claude-3-5-haiku-20241022-v1:0
# - amazon.titan-embed-text-v2:0

# Python 의존성
pip install boto3
```

## 통합 실행

```bash
# 4개 빌드 스크립트를 순차 실행
python scripts/builders/build_all.py

# LLM 호출 없이 흐름만 확인 (테스트용)
python scripts/builders/build_all.py --dry-run

# 일부 스킵 (예: 슬롯 카드는 이미 있어서 review만 다시)
python scripts/builders/build_all.py --skip slots safety forbidden
```

## 개별 스크립트

### 1. build_slot_cards.py
호흡기 87개 증상 슬롯 카드 정의·예시 생성.

```bash
python scripts/builders/build_slot_cards.py --output data/slot_cards.json
```

- 입력: 시드 리스트 (스크립트 내 정의)
- 출력: `data/slot_cards.json`
- 비용: 약 $0.30
- 시간: 약 30분

### 2. build_review_templates.py
각 슬롯의 의료진 확인 항목 + 조건부 우선순위 생성.

```bash
python scripts/builders/build_review_templates.py --input data/slot_cards.json
```

- 입력: `data/slot_cards.json` (build_slot_cards 결과)
- 출력: `data/slot_cards.json` 덮어쓰기 (review_template 필드 추가)
- 비용: 약 $0.50
- 시간: 약 20분

### 3. build_safety_keywords.py
응급의학 기반 위험 키워드 6 카테고리 + False Positive 방지 규칙.

```bash
python scripts/builders/build_safety_keywords.py --output data/safety_keywords.json
```

- 출력: `data/safety_keywords.json`
- 비용: 약 $0.05
- 시간: 약 5분

### 4. build_forbidden_outputs.py
진단·처방 권유 금지 패턴 사전.

```bash
python scripts/builders/build_forbidden_outputs.py --output data/forbidden_outputs.json
```

- 출력: `data/forbidden_outputs.json`
- 비용: 약 $0.05
- 시간: 약 5분

## 검수

빌드 후 결과 JSON을 일반 개발자가 다음 항목으로 검토:

- [ ] 슬롯의 positive_examples에 사투리·구어체가 포함되어 있는가 (예: "맥혀요")
- [ ] review_template이 임상적으로 합리적으로 보이는가 (의학 상식 수준)
- [ ] 위험 키워드 false_positive_excludes에 명백한 일반 단어가 포함되어 있는가 (예: "피곤", "피로")
- [ ] 금지 패턴이 실제 진단·처방 문구를 차단하는가

의료진 추가 검수가 가능하면 시연 리허설 시 묶음 검토(1~2시간) 권장.

## Tool Use 기반 안정성

모든 빌드 스크립트는 Bedrock Converse API의 Tool Use(JSON Schema 강제)를 사용합니다. 프롬프트로 "JSON 출력하세요" 부탁하는 방식 대비 다음 효과:

- enum 위반 불가능 (severity는 항상 high/medium 중 하나)
- required 필드 누락 불가능
- 추가 필드 자동 제거
- JSON 파싱 에러 사실상 0

## 트러블슈팅

**Bedrock AccessDeniedException**
- AWS 콘솔 → Bedrock → Model access에서 Claude Sonnet 활성화 확인

**Rate limit 에러**
- 스크립트에 `time.sleep(0.5)` 있음. 더 늘리려면 코드 수정
- 대량 빌드 시 `--region us-east-1` 등 다른 리전 사용 검토

**JSON 파싱 에러**
- Tool Use를 쓰므로 거의 발생하지 않으나, 발생 시 모델 버전 확인
- Claude 3 계열만 Tool Use 정상 지원
