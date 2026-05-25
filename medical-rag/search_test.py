"""
search_test.py
로컬 Docker OpenSearch에서 BM25 / 시맨틱 검색 결과를 비교 출력
"""

import boto3
import json
from opensearchpy import OpenSearch, RequestsHttpConnection

# ── 설정 ──────────────────────────────────────────────────
REGION          = "ap-northeast-2"
OPENSEARCH_HOST = "localhost"
OPENSEARCH_PORT = 9200
INDEX_NAME      = "diseases"
EMBED_MODEL     = "amazon.titan-embed-text-v2:0"

# ── 클라이언트 ─────────────────────────────────────────────
bedrock = boto3.client("bedrock-runtime", region_name=REGION)

os_client = OpenSearch(
    hosts=[{"host": OPENSEARCH_HOST, "port": OPENSEARCH_PORT}],
    use_ssl=False,
    verify_certs=False,
    ssl_show_warn=False,
    connection_class=RequestsHttpConnection,
)


# ── Titan 임베딩 ───────────────────────────────────────────
def get_embedding(text):
    response = bedrock.invoke_model(
        modelId=EMBED_MODEL,
        body=json.dumps({"inputText": text, "dimensions": 1024, "normalize": True})
    )
    return json.loads(response["body"].read())["embedding"]


# ── BM25 검색 ─────────────────────────────────────────────
def bm25_search(query, k=3):
    response = os_client.search(
        index=INDEX_NAME,
        body={
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["symptoms_text", "mapped_symptoms_text", "symptom_desc", "name_ko"]
                }
            },
            "size": k
        }
    )
    return [(h["_source"]["name_ko"], h["_score"]) for h in response["hits"]["hits"]]


# ── 시맨틱 검색 ───────────────────────────────────────────
def semantic_search(query, k=3):
    embedding = get_embedding(query)
    response = os_client.search(
        index=INDEX_NAME,
        body={
            "query": {
                "knn": {
                    "embedding": {"vector": embedding, "k": k}
                }
            },
            "size": k
        }
    )
    return [(h["_source"]["name_ko"], h["_score"]) for h in response["hits"]["hits"]]


# ── 테스트 ─────────────────────────────────────────────────
if __name__ == "__main__":
    queries = [
        "기침이 심하고 숨이 차요",
        "피가 섞인 가래가 나와요",
        "열이 나고 체중이 줄었어요"
    ]

    for query in queries:
        print(f"\n{'='*50}")
        print(f"검색어: {query}")

        print("\n[BM25 결과]")
        for name, score in bm25_search(query):
            print(f"  {name} (점수: {score:.2f})")

        print("\n[시맨틱 결과]")
        for name, score in semantic_search(query):
            print(f"  {name} (점수: {score:.4f})")
