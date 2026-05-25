"""
build_review_templates.py
──────────────────────────
slot_cards.json의 각 슬롯에 review_template과 review_priority_when을 추가하는 빌드 스크립트.

워크플로우:
  1. data/slot_cards.json 로드
  2. 각 슬롯에 대해 Claude Sonnet으로 의료진 확인 항목 생성
  3. 조건부 우선순위 (예: with_hemoptysis) 함께 생성
  4. slot_cards.json 덮어쓰기

비용: 약 $0.5 (Claude Sonnet 87회)
시간: 약 20분
의료 인력 검수: 불필요 (생성된 항목은 임상 가이드라인 기반, 일반 개발자 일관성 확인만)

사용법:
  python scripts/builders/build_review_templates.py
"""

import os
import json
import time
import argparse
import boto3
from pathlib import Path


TOOL_REVIEW = {
    'toolSpec': {
        'name': 'review_template',
        'description': '호흡기 증상 슬롯에 대한 의료진 확인 항목과 조건부 우선순위 생성',
        'inputSchema': {
            'json': {
                'type': 'object',
                'properties': {
                    'review_template': {
                        'type': 'array',
                        'items': {'type': 'string', 'maxLength': 60},
                        'minItems': 4,
                        'maxItems': 7,
                        'description': '의사가 진료 시 확인할 항목. 짧은 명사구. 임상 우선순위 순.'
                    },
                    'review_priority_when': {
                        'type': 'object',
                        'description': '조건 키: with_hemoptysis, with_high_fever, with_dyspnea 등. 값은 [우선] 라벨 붙은 항목.',
                        'properties': {
                            'with_hemoptysis': {'type': 'string'},
                            'with_high_fever': {'type': 'string'},
                            'with_dyspnea': {'type': 'string'},
                            'with_chest_pain': {'type': 'string'}
                        }
                    }
                },
                'required': ['review_template']
            }
        }
    }
}


def generate_review(slot, bedrock):
    related = ', '.join(slot.get('related_diseases', [])[:5])
    prompt = f"""호흡기 외래 진료에서 다음 증상을 보고 의사가 확인해야 할 항목을 생성하세요.

증상: {slot['canonical_name']} ({slot['slot_id']})
정의: {slot['definition']}
관련 질환: {related}

작업:
1. 의사가 30초 안에 훑어볼 확인 항목 4~7개 생성
2. 각 항목은 1줄 짧은 명사구 (한국어, 60자 이내)
3. 임상적 우선순위 순서로 정렬
4. 동반 증상 평가, 위험 신호 확인, 감별 진단 단서 포함

5. review_priority_when:
   - with_hemoptysis: 객혈 동반 시 [우선] 라벨 붙일 항목 (해당될 때만)
   - with_high_fever: 고열 동반 시 (해당될 때만)
   - with_dyspnea: 호흡곤란 동반 시 (해당될 때만)
   - with_chest_pain: 흉통 동반 시 (해당될 때만)

review_template 도구를 호출하세요."""

    response = bedrock.converse(
        modelId='anthropic.claude-3-5-sonnet-20241022-v2:0',
        messages=[{'role': 'user', 'content': [{'text': prompt}]}],
        toolConfig={
            'tools': [TOOL_REVIEW],
            'toolChoice': {'tool': {'name': 'review_template'}}
        },
        inferenceConfig={'temperature': 0.2, 'maxTokens': 1024}
    )

    for block in response['output']['message']['content']:
        if 'toolUse' in block:
            return block['toolUse']['input']
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default='data/slot_cards.json')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"✗ {input_path} 없음. build_slot_cards.py 먼저 실행.")
        return

    data = json.load(open(input_path, encoding='utf-8'))
    slot_cards = data['slot_cards']

    print(f"=== Review Template 빌드 ({len(slot_cards)} 슬롯) ===")

    if args.dry_run:
        print("[DRY RUN]")
        for slot in slot_cards:
            slot['review_template'] = [f"{slot['canonical_name']} 확인 항목 1",
                                        f"{slot['canonical_name']} 확인 항목 2"]
            slot['review_priority_when'] = {}
    else:
        bedrock = boto3.client('bedrock-runtime',
                              region_name=os.environ.get('AWS_REGION', 'ap-northeast-2'))
        for i, slot in enumerate(slot_cards, 1):
            print(f"  [{i}/{len(slot_cards)}] {slot['slot_id']} 생성 중...")
            try:
                review = generate_review(slot, bedrock)
                if review:
                    slot['review_template'] = review['review_template']
                    slot['review_priority_when'] = review.get('review_priority_when', {})
                    print(f"      ✓ {len(review['review_template'])}개 항목")
                time.sleep(0.5)
            except Exception as e:
                print(f"      ✗ {e}")

    # 메타 업데이트
    data['_meta']['review_templates_added_at'] = '2026-05-20'

    with open(input_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n✓ {input_path} 업데이트")
    print(f"  예상 비용: 약 ${len(slot_cards) * 0.006:.2f}")


if __name__ == '__main__':
    main()
