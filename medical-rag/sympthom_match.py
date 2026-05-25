"""
sympthom_match.py
환자 자연어 입력 → 로컬 Docker OpenSearch (BM25 + KNN 하이브리드) → Claude로 공식 증상명 매핑
"""

import boto3
import json
from opensearchpy import OpenSearch, RequestsHttpConnection

# ── 설정 ──────────────────────────────────────────────────
REGION          = "ap-northeast-2"
OPENSEARCH_HOST = "localhost"
OPENSEARCH_PORT = 9200
INDEX_NAME      = "diseases"

LLM_MODEL   = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
EMBED_MODEL = "amazon.titan-embed-text-v2:0"

# ── 클라이언트 ─────────────────────────────────────────────
bedrock = boto3.client("bedrock-runtime", region_name=REGION)

os_client = OpenSearch(
    hosts=[{"host": OPENSEARCH_HOST, "port": OPENSEARCH_PORT}],
    use_ssl=False,
    verify_certs=False,
    ssl_show_warn=False,
    connection_class=RequestsHttpConnection,
)


# ── 임베딩 ─────────────────────────────────────────────────
def get_embedding(text):
    response = bedrock.invoke_model(
        modelId=EMBED_MODEL,
        body=json.dumps({"inputText": text, "dimensions": 1024, "normalize": True})
    )
    return json.loads(response["body"].read())["embedding"]


# ── BM25 검색 ─────────────────────────────────────────────
def bm25_search(query, k=5):
    response = os_client.search(
        index=INDEX_NAME,
        body={
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["symptoms_text", "mapped_symptoms_text", "symptom_desc"]
                }
            },
            "size": k
        }
    )
    return [h["_source"] for h in response["hits"]["hits"]]


# ── 시맨틱 검색 ───────────────────────────────────────────
def semantic_search(query, k=5):
    embedding = get_embedding(query)
    response = os_client.search(
        index=INDEX_NAME,
        body={
            "query": {
                "knn": {"embedding": {"vector": embedding, "k": k}}
            },
            "size": k
        }
    )
    return [h["_source"] for h in response["hits"]["hits"]]


# ── 하이브리드 (RRF) ──────────────────────────────────────
def hybrid_search(query, k=3):
    bm25_results     = bm25_search(query, k=5)
    semantic_results = semantic_search(query, k=5)

    rrf_scores = {}
    for rank, doc in enumerate(bm25_results):
        did = doc["disease_id"]
        rrf_scores[did] = rrf_scores.get(did, {"doc": doc, "score": 0})
        rrf_scores[did]["score"] += 1 / (60 + rank + 1)

    for rank, doc in enumerate(semantic_results):
        did = doc["disease_id"]
        if did not in rrf_scores:
            rrf_scores[did] = {"doc": doc, "score": 0}
        rrf_scores[did]["score"] += 0.7 / (60 + rank + 1)

    sorted_docs = sorted(rrf_scores.values(), key=lambda x: x["score"], reverse=True)
    return [item["doc"] for item in sorted_docs[:k]]


# ── 증상 매핑 (Claude 호출) ───────────────────────────────
def match_symptom_names(patient_input):
    docs = hybrid_search(patient_input, k=3)

    context = ""
    all_symptoms = []
    for doc in docs:
        symptoms = doc.get("symptoms", [])
        all_symptoms.extend(symptoms)
        context += "\n질병명: " + doc["name_ko"]
        context += "\n공식 증상명: " + ", ".join(symptoms)
        context += "\n증상 설명: " + doc.get("symptom_desc", "") + "\n"

    all_symptoms = list(set(all_symptoms))

    prompt = "당신은 의료 증상 분류 전문가입니다.\n"
    prompt += "환자가 말한 내용을 분석해서 아래 공식 증상명 중 해당하는 것을 찾아주세요.\n\n"
    prompt += "[참고 문서]\n" + context + "\n"
    prompt += "[전체 공식 증상명 목록]\n" + ", ".join(all_symptoms) + "\n\n"
    prompt += "[환자가 말한 내용]\n" + patient_input + "\n\n"
    prompt += '공식 증상명 목록에서 환자 증상과 관련된 것만 골라서 아래 JSON 형식으로만 답하세요. JSON 외의 텍스트는 출력하지 마세요.\n'
    prompt += '{"matched_symptoms": ["증상명1", "증상명2"], "reason": "이유"}'

    response = bedrock.invoke_model(
        modelId=LLM_MODEL,
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 500,
            "temperature": 0.1,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        })
    )
    result = json.loads(response["body"].read())
    answer = result["content"][0]["text"].strip()

    try:
        start  = answer.find("{")
        end    = answer.rfind("}") + 1
        parsed = json.loads(answer[start:end])
    except Exception:
        parsed = {"matched_symptoms": [], "reason": answer}

    return parsed, docs


if __name__ == "__main__":
    test_inputs = [
        "기침이 심하고 숨이 차요",
        "피가 섞인 가래가 나와요",
        "열이 나고 체중이 많이 줄었어요"
    ]

    for patient_input in test_inputs:
        print("\n" + "="*50)
        print("환자 입력: " + patient_input)

        result, docs = match_symptom_names(patient_input)

        print("\n[참고한 질병]")
        for doc in docs:
            print("  - " + doc["name_ko"])

        print("\n[매핑된 공식 증상명]")
        for s in result.get("matched_symptoms", []):
            print("  v " + s)

        print("\n[이유] " + result.get("reason", ""))
