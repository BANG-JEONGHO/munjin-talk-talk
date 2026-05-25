# medical-rag (로컬 Docker OpenSearch 버전)

질병/증상 데이터를 로컬 OpenSearch(도커)에 임베딩 저장하고, 환자 자연어 입력을 공식 증상명으로 매핑하는 RAG 파이프라인.

벡터 DB는 로컬 Docker 컨테이너로 띄우므로 **유휴 시간에 `docker compose down` 하면 비용 0**.

## 구성

| 파일 | 역할 |
| --- | --- |
| `docker-compose.yml` | OpenSearch 2.13 single-node (보안 비활성, KNN 가능) |
| `diseases_cleaned.json` | 원본 질병/증상 데이터 (63개) |
| `embed_diseases.py` | 데이터 → Bedrock Titan 임베딩 → OpenSearch 인덱싱 |
| `search_test.py` | BM25 / 시맨틱 검색 결과 비교 (스모크 테스트) |
| `sympthom_match.py` | 하이브리드 검색(RRF) + Claude Haiku로 공식 증상명 매핑 |

## 사전 준비

1. Docker Desktop (또는 colima 등 Docker 데몬) 실행 중이어야 합니다.
2. AWS 자격증명이 환경에 설정되어 있어야 합니다 (`~/.aws/credentials` 또는 환경변수).
3. AWS Bedrock에서 다음 모델 액세스가 승인되어 있어야 합니다 (서울 리전 기준):
   - `amazon.titan-embed-text-v2:0`
   - `global.anthropic.claude-haiku-4-5-20251001-v1:0` (또는 사용 가능한 다른 Claude 모델)

## 실행 순서

```bash
# 1) OpenSearch 컨테이너 기동 (최초 1회 또는 작업 시작 시)
docker compose up -d

# 2) 헬스체크 확인 (선택)
curl -s http://localhost:9200 | python3 -m json.tool

# 3) Python 의존성 (venv 안에서)
source venv/bin/activate
pip install boto3 opensearch-py requests

# 4) 임베딩 + 인덱싱 (최초 1회 또는 데이터가 바뀐 경우)
python3 embed_diseases.py

# 5) 검색 동작 확인
python3 search_test.py

# 6) 메인 시나리오 실행
python3 sympthom_match.py

# 작업 끝나면 (비용/리소스 절약)
docker compose down
#  → 데이터는 named volume(opensearch-data)에 영속됩니다.
#    완전히 비우려면: docker compose down -v
```

## 자주 만나는 문제

**`OpenSearch에 연결할 수 없습니다`**
컨테이너가 아직 부팅 중일 수 있습니다. `docker compose ps` 로 상태(`healthy`) 확인. 처음 기동은 30초~1분 걸립니다.

**`ValidationException: model identifier is invalid`**
서울 리전 Bedrock에서 해당 모델 액세스가 승인 안 됐거나 모델 ID가 바뀐 경우. 사용 가능한 모델은 아래 명령으로 확인:
```bash
python3 -c "
import boto3
c = boto3.client('bedrock', region_name='ap-northeast-2')
for p in c.list_inference_profiles().get('inferenceProfileSummaries', []):
    print(p['inferenceProfileId'])
"
```

**메모리 부족으로 컨테이너가 죽는다면**
`docker-compose.yml` 의 `OPENSEARCH_JAVA_OPTS` 의 `-Xms512m -Xmx512m` 을 더 작게 (예: `256m`) 또는 더 크게 조정.
