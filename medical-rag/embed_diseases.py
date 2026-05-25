"""
embed_diseases.py
diseases_cleaned.json → 증상 매핑 → Titan 임베딩 → 로컬 Docker OpenSearch 저장
"""

import boto3
import json
import time
from opensearchpy import OpenSearch, RequestsHttpConnection

# ── 설정 ──────────────────────────────────────────────────
REGION         = "ap-northeast-2"            # Bedrock 호출 리전
OPENSEARCH_HOST = "localhost"                # docker compose로 띄운 로컬 OpenSearch
OPENSEARCH_PORT = 9200
INDEX_NAME      = "diseases"
DATA_FILE       = "diseases_cleaned.json"

# ── AWS 클라이언트 (Bedrock 임베딩용) ──────────────────────
bedrock = boto3.client("bedrock-runtime", region_name=REGION)

# ── 로컬 OpenSearch 클라이언트 (인증/SSL 없음) ─────────────
os_client = OpenSearch(
    hosts=[{"host": OPENSEARCH_HOST, "port": OPENSEARCH_PORT}],
    use_ssl=False,
    verify_certs=False,
    ssl_show_warn=False,
    connection_class=RequestsHttpConnection,
)


# ── 1. 증상 매핑 ───────────────────────────────────────────
def map_symptoms(disease):
    symptom_list = disease.get("symptoms", [])
    description  = disease.get("sections", {}).get("symptom", "")

    matched   = [s for s in symptom_list if s in description]
    unmatched = [s for s in symptom_list if s not in description]

    return matched, unmatched, description


# ── 2. Titan 임베딩 ────────────────────────────────────────
def get_embedding(text: str) -> list:
    response = bedrock.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        body=json.dumps({
            "inputText": text,
            "dimensions": 1024,
            "normalize": True,
        }),
    )
    return json.loads(response["body"].read())["embedding"]


# ── 3. 임베딩용 텍스트 구성 ────────────────────────────────
def build_embed_text(disease, matched_symptoms):
    sections = disease.get("sections", {})

    return f"""
질병명: {disease['name_ko']}
카테고리: {disease.get('category', '')}
진료과: {', '.join(disease.get('departments', []))}
전체 증상: {', '.join(disease.get('symptoms', []))}
설명에서 확인된 증상: {', '.join(matched_symptoms)}
증상 설명: {sections.get('symptom', '')}
정의: {sections.get('definition', '')[:300]}
""".strip()


# ── 4. OpenSearch 인덱스 생성 ──────────────────────────────
def create_index():
    if os_client.indices.exists(index=INDEX_NAME):
        print(f"기존 인덱스 '{INDEX_NAME}' 삭제 후 재생성")
        os_client.indices.delete(index=INDEX_NAME)

    os_client.indices.create(
        index=INDEX_NAME,
        body={
            "settings": {
                "index": {"knn": True},
                "analysis": {
                    "analyzer": {
                        "korean": {"type": "standard"}
                    }
                },
            },
            "mappings": {
                "properties": {
                    "name_ko":               {"type": "text",       "analyzer": "korean"},
                    "symptoms_text":         {"type": "text",       "analyzer": "korean"},
                    "mapped_symptoms_text":  {"type": "text",       "analyzer": "korean"},
                    "symptom_desc":          {"type": "text",       "analyzer": "korean"},
                    "disease_id":            {"type": "keyword"},
                    "category":              {"type": "keyword"},
                    "departments":           {"type": "keyword"},
                    "symptoms":              {"type": "keyword"},
                    "mapped_symptoms":       {"type": "keyword"},
                    "embedding": {
                        "type":      "knn_vector",
                        "dimension": 1024,
                    },
                }
            },
        },
    )
    print(f"인덱스 '{INDEX_NAME}' 생성 완료")


# ── 5. 문서 저장 ───────────────────────────────────────────
def index_disease(disease):
    matched, unmatched, desc = map_symptoms(disease)
    embed_text = build_embed_text(disease, matched)
    embedding  = get_embedding(embed_text)

    doc = {
        "name_ko":               disease["name_ko"],
        "symptoms_text":         ", ".join(disease.get("symptoms", [])),
        "mapped_symptoms_text":  ", ".join(matched),
        "symptom_desc":          desc,
        "disease_id":            disease["disease_id"],
        "category":              disease.get("category", ""),
        "departments":           disease.get("departments", []),
        "symptoms":              disease.get("symptoms", []),
        "mapped_symptoms":       matched,
        "source_url":            disease.get("source_url", ""),
        "embedding":             embedding,
    }

    os_client.index(
        index=INDEX_NAME,
        id=disease["disease_id"],
        body=doc,
    )

    return matched, unmatched


# ── 6. 메인 실행 ───────────────────────────────────────────
def main():
    print("=" * 50)
    print("diseases_cleaned.json 임베딩 시작 (로컬 OpenSearch)")
    print("=" * 50)

    # OpenSearch 연결 확인
    try:
        info = os_client.info()
        print(f"OpenSearch 연결됨: {info.get('version', {}).get('number')}\n")
    except Exception as e:
        print(f"[에러] OpenSearch에 연결할 수 없습니다: {e}")
        print("docker compose up -d 로 컨테이너를 먼저 띄워주세요.")
        return

    with open(DATA_FILE, encoding="utf-8") as f:
        diseases = json.load(f)

    print(f"총 {len(diseases)}개 질병 로드\n")

    create_index()
    print()

    for i, disease in enumerate(diseases, 1):
        name = disease["name_ko"]
        try:
            matched, unmatched = index_disease(disease)
            print(f"[{i:2d}/{len(diseases)}] OK {name}")
            print(f"         매핑된 증상:  {matched}")
            if unmatched:
                print(f"         미매핑 증상:  {unmatched}")
        except Exception as e:
            print(f"[{i:2d}/{len(diseases)}] FAIL {name}: {e}")

        # Bedrock API 속도 제한 방지
        time.sleep(0.3)

    print("\n" + "=" * 50)
    print(f"임베딩 완료! 총 {len(diseases)}개 질병 저장 시도")
    print("=" * 50)

    time.sleep(1)
    os_client.indices.refresh(index=INDEX_NAME)
    count = os_client.count(index=INDEX_NAME)["count"]
    print(f"OpenSearch 저장된 문서 수: {count}개")


if __name__ == "__main__":
    main()
