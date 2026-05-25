"""
upload_url Lambda
─────────────────
POST /upload-url

환자가 음성 녹음을 마치고 S3에 직접 업로드할 수 있도록
presigned PUT URL을 발급한다. Lambda를 거치지 않고
브라우저가 직접 S3에 업로드하므로 비용·시간 절감.

요청 페이로드:
{
  "session_id": "s-1747120000-abc12",
  "question_id": "Q1",
  "visit_type": "initial",         // 또는 "followup"
  "content_type": "audio/webm"
}

응답 페이로드:
{
  "upload_url": "https://munjin-audio.s3.amazonaws.com/...",
  "s3_key": "sessions/s-xxx/Q1.webm",
  "expires_in": 300
}

부수 효과:
- DynamoDB sessions 테이블에 세션 레코드 초기화 (없을 때만)
"""

import os
import json
import boto3
from datetime import datetime, timezone

s3 = boto3.client('s3')
ddb = boto3.client('dynamodb')

BUCKET = os.environ.get('AUDIO_BUCKET', 'munjin-audio')
TABLE = os.environ.get('SESSIONS_TABLE', 'sessions')
EXPIRES_IN = 300  # 5분


def handler(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
    except json.JSONDecodeError:
        return _resp(400, {'error': 'invalid_json'})

    session_id = body.get('session_id')
    question_id = body.get('question_id')
    visit_type = body.get('visit_type', 'initial')
    content_type = body.get('content_type', 'audio/webm')

    if not session_id or not question_id:
        return _resp(400, {'error': 'missing_required_fields'})

    if visit_type not in ('initial', 'followup'):
        return _resp(400, {'error': 'invalid_visit_type'})

    if question_id not in ('Q1', 'Q2', 'Q3', 'Q4'):
        return _resp(400, {'error': 'invalid_question_id'})

    # S3 키 형식: sessions/{session_id}/{question_id}.webm
    s3_key = f"sessions/{session_id}/{question_id}.webm"

    # presigned PUT URL 발급
    try:
        url = s3.generate_presigned_url(
            ClientMethod='put_object',
            Params={
                'Bucket': BUCKET,
                'Key': s3_key,
                'ContentType': content_type
            },
            ExpiresIn=EXPIRES_IN,
        )
    except Exception as e:
        return _resp(500, {'error': 'presign_failed', 'detail': str(e)})

    # 세션 레코드 초기화 (이미 있으면 건너뜀)
    now = datetime.now(timezone.utc).isoformat()
    try:
        ddb.put_item(
            TableName=TABLE,
            Item={
                'session_id': {'S': session_id},
                'visit_type': {'S': visit_type},
                'created_at': {'S': now},
                'schema_version': {'S': '1.0'},
                'responses': {'M': {
                    'Q1': {'NULL': True},
                    'Q2': {'NULL': True},
                    'Q3': {'NULL': True},
                    'Q4': {'NULL': True},
                }},
                'safety_flag': {'NULL': True},
                'validator_passed': {'NULL': True},
                'doctor_review': {'NULL': True},
                'patient_guide': {'NULL': True},
            },
            ConditionExpression='attribute_not_exists(session_id)'
        )
    except ddb.exceptions.ConditionalCheckFailedException:
        # 이미 존재. 정상.
        pass
    except Exception as e:
        # DDB 에러는 로그만 남기고 진행 (URL 발급은 성공 처리)
        print(f"[WARN] DDB init failed: {e}")

    return _resp(200, {
        'upload_url': url,
        's3_key': s3_key,
        'expires_in': EXPIRES_IN
    })


def _resp(status, body):
    return {
        'statusCode': status,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST,OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
        },
        'body': json.dumps(body, ensure_ascii=False)
    }
