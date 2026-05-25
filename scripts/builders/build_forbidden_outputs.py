"""
build_forbidden_outputs.py
───────────────────────────
의료 AI 출력에서 차단해야 할 패턴(진단·처방·치료 권유) 사전을 자동 생성하는
빌드 스크립트. Validator의 4단계(금지 패턴 검사)에서 사용.

워크플로우:
  1. Claude Sonnet에게 의료법·의료 안전 가이드라인 기반 금지 표현 생성 요청
  2. 4 카테고리 (diagnosis, prescription, treatment_recommendation, emergency_routing)
  3. data/forbidden_outputs.json으로 저장

비용: 약 $0.05
시간: 약 5분
의료 인력 검수: 불필요 (일반 상식 수준 검토 가능)

사용법:
  python scripts/builders/build_forbidden_outputs.py
"""

import os
import json
import argparse
import boto3
from pathlib import Path


TOOL_FORBIDDEN = {
    'toolSpec': {
        'name': 'forbidden_patterns',
        'description': '의료 AI 출력에서 차단해야 할 정규식 패턴 사전 생성',
        'inputSchema': {
            'json': {
                'type': 'object',
                'properties': {
                    'categories': {
                        'type': 'object',
                        'properties': {
                            'diagnosis': {'$ref': '#/$defs/pattern_list'},
                            'prescription': {'$ref': '#/$defs/pattern_list'},
                            'treatment_recommendation': {'$ref': '#/$defs/pattern_list'},
                            'emergency_routing': {'$ref': '#/$defs/pattern_list'}
                        },
                        'required': ['diagnosis', 'prescription',
                                    'treatment_recommendation', 'emergency_routing']
                    }
                },
                'required': ['categories'],
                '$defs': {
                    'pattern_list': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'pattern': {
                                    'type': 'string',
                                    'description': '한국어 정규식 패턴'
                                },
                                'reason': {
                                    'type': 'string',
                                    'description': '왜 차단해야 하는가'
                                },
                                'example_violation': {
                                    'type': 'string',
                                    'description': '이 패턴에 매칭될 위반 표현 예시'
                                }
                            },
                            'required': ['pattern', 'reason', 'example_violation']
                        },
                        'minItems': 4,
                        'maxItems': 10
                    }
                }
            }
        }
    }
}


PROMPT = """당신은 의료 안전 가이드라인 전문가입니다.
한국어 의료 AI 시스템이 출력하면 안 되는 텍스트 패턴 목록을 정규식으로 생성하세요.

배경:
- 이 AI는 환자 발화를 의사에게 전달하는 인수인계 시스템입니다
- AI는 진단·처방·치료를 제안하면 의료법 위반이 될 수 있습니다
- AI는 응급실 안내·입원 권유를 단독으로 결정하면 안 됩니다
- AI는 약 이름이나 복용법을 단독으로 추천하면 안 됩니다

4 카테고리:

1. diagnosis: 진단명을 단정하는 표현
   예시: "감기입니다", "(어떤)병입니다", "확진"
   패턴: (.+)병(?:입니다|이에요), 확진, ...

2. prescription: 약 처방·복용 권유
   예시: "혈압약을 드세요", "처방을 권장드립니다"
   패턴: 처방.{0,3}(권장|추천|드립니다), 약을 드세요, ...

3. treatment_recommendation: 치료·검사·수술 권유
   예시: "수술을 권장합니다", "검사를 받으세요"
   패턴: 수술.{0,3}권장, 검사.{0,3}받으세요, ...

4. emergency_routing: 응급실·입원 권유
   예시: "응급실 가세요", "입원하세요"
   패턴: 응급실.{0,3}가세요, 입원.{0,3}하세요, ...

각 카테고리당 5~10개 패턴을 생성하고, 각 패턴에 reason과 example_violation 포함.

forbidden_patterns 도구를 호출하세요."""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='data/forbidden_outputs.json')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    if args.dry_run:
        print("[DRY RUN]")
        return

    bedrock = boto3.client('bedrock-runtime',
                          region_name=os.environ.get('AWS_REGION', 'ap-northeast-2'))

    print("=== 금지 출력 패턴 빌드 ===")
    response = bedrock.converse(
        modelId='anthropic.claude-3-5-sonnet-20241022-v2:0',
        messages=[{'role': 'user', 'content': [{'text': PROMPT}]}],
        toolConfig={
            'tools': [TOOL_FORBIDDEN],
            'toolChoice': {'tool': {'name': 'forbidden_patterns'}}
        },
        inferenceConfig={'temperature': 0.2, 'maxTokens': 3072}
    )

    result = None
    for block in response['output']['message']['content']:
        if 'toolUse' in block:
            result = block['toolUse']['input']
            break

    if not result:
        print("✗ LLM 응답 없음")
        return

    # Validator가 사용할 평탄한 패턴 리스트도 함께 생성
    all_patterns = []
    for cat_patterns in result['categories'].values():
        all_patterns.extend([p['pattern'] for p in cat_patterns])

    final = {
        '_meta': {
            'version': '2.0',
            'generated_by': 'build_forbidden_outputs.py + Claude Sonnet',
            'note': '의료 안전 가이드라인 기반 LLM 자동 생성',
            'applies_to': ['matched_slots', 'structured', 'patient_guide', 'doctor_review (LLM 변환분)'],
            'total_patterns': len(all_patterns)
        },
        'patterns': all_patterns,
        '_categories': result['categories']  # 카테고리별 세부 정보 (debugging용)
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(final, f, ensure_ascii=False, indent=2)

    print(f"✓ 저장: {output_path}")
    print(f"  카테고리: {len(result['categories'])}")
    print(f"  총 패턴: {len(all_patterns)}")
    print(f"  예상 비용: 약 $0.05")


if __name__ == '__main__':
    main()
