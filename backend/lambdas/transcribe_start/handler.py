"""
Lambda: transcribe_start
─────────────────────────
1) 클라이언트에 S3 PUT presigned URL을 발급
2) 동시에 Amazon Transcribe 작업명을 예약 (audio 업로드 완료 시 별도 트리거)

실제 워크플로우:
1. 프론트가 POST /upload-url → 이 Lambda → presigned URL + jobName 반환
2. 프론트가 S3에 PUT (브라우저에서 직접)
3. S3 이벤트 → start-transcribe-job 트리거 (이 Lambda의 두 번째 핸들러 또는 별도)
4. 프론트가 GET /transcribe-result?jobName=... → 결과 확인

MVP에서는 1단계만 처리. S3 이벤트 핸들러는 Step Functions 또는 SQS로 분리 권장.
"""

import json
import os
import uuid
import boto3
from botocore.config import Config

REGION = os.environ.get("AWS_REGION", "ap-northeast-2")
AUDIO_BUCKET = os.environ.get("AUDIO_BUCKET", "munjin-tok-tok-audio-temp")
CUSTOM_VOCAB_NAME = os.environ.get("CUSTOM_VOCAB_NAME", "")  # 강원 사투리 사전 (Transcribe에 사전 등록)

s3 = boto3.client("s3", region_name=REGION, config=Config(signature_version="s3v4"))
transcribe = boto3.client("transcribe", region_name=REGION)


def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body", "{}")) if "body" in event else event
        session_id = body["session_id"]
        question_id = body["question_id"]
        content_type = body.get("content_type", "audio/webm")

        # S3 key
        ext = content_type.split("/")[-1]
        s3_key = f"sessions/{session_id}/{question_id}.{ext}"
        job_name = f"munjin-{session_id}-{question_id}-{uuid.uuid4().hex[:6]}"

        # Presigned PUT URL 발급 (5분 유효)
        presigned = s3.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": AUDIO_BUCKET,
                "Key": s3_key,
                "ContentType": content_type
            },
            ExpiresIn=300
        )

        return _response(200, {
            "upload_url": presigned,
            "s3_key": s3_key,
            "transcribe_job_name": job_name,
            "bucket": AUDIO_BUCKET
        })

    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}")
        return _response(500, {"error": str(e)})


def start_transcription_handler(event, context):
    """
    S3 이벤트 트리거로 호출되는 핸들러.
    음성 업로드 완료 시 Transcribe 작업 시작.
    """
    try:
        for record in event["Records"]:
            bucket = record["s3"]["bucket"]["name"]
            key = record["s3"]["object"]["key"]
            # key: sessions/{session_id}/{question_id}.webm
            parts = key.split("/")
            session_id = parts[1]
            question_id = parts[2].split(".")[0]
            job_name = f"munjin-{session_id}-{question_id}-{uuid.uuid4().hex[:6]}"

            params = {
                "TranscriptionJobName": job_name,
                "LanguageCode": "ko-KR",
                "MediaFormat": "webm",
                "Media": {"MediaFileUri": f"s3://{bucket}/{key}"},
                "OutputBucketName": bucket,
                "OutputKey": f"transcripts/{session_id}/{question_id}.json"
            }

            # Custom Vocabulary가 등록되어 있다면 사용
            if CUSTOM_VOCAB_NAME:
                params["Settings"] = {"VocabularyName": CUSTOM_VOCAB_NAME}

            transcribe.start_transcription_job(**params)
            print(f"[transcribe] Job started: {job_name}")

        return {"statusCode": 200}

    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}")
        return {"statusCode": 500, "body": str(e)}


def _response(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(body, ensure_ascii=False)
    }
