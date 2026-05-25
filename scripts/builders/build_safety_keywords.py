"""
build_safety_keywords.py
─────────────────────────
응급의학 가이드라인 기반으로 위험 키워드 사전과 False Positive 방지 규칙을
자동 생성하는 빌드 스크립트.

워크플로우:
  1. 6개 위험 카테고리 정의 (hemoptysis, severe_dyspnea, ...)
  2. Claude Sonnet으로 각 카테고리의 패턴과 false_positive_excludes 생성
  3. data/safety_keywords.json으로 저장

비용: 약 $0.05 (Claude Sonnet 1회 통합 호출)
시간: 약 5분
의료 인력 검수: 불필요

사용법:
  python scripts/builders/build_safety_keywords.py
"""

import os
import json
import argparse
import boto3
from pathlib import Path


TOOL_SAFETY_KEYWORDS = {
    'toolSpec': {
        'name': 'safety_keywords_set',
        'description': '응급의학 가이드라인 기반 위험 키워드 사전 생성',
        'inputSchema': {
            'json': {
                'type': 'object',
                'properties': {
                    'categories': {
                        'type': 'object',
                        'properties': {
                            'hemoptysis': {'$ref': '#/$defs/category'},
                            'severe_dyspnea': {'$ref': '#/$defs/category'},
                            'consciousness_change': {'$ref': '#/$defs/category'},
                            'severe_chest_pain': {'$ref': '#/$defs/category'},
                            'high_fever': {'$ref': '#/$defs/category'},
                            'anaphylaxis_signs': {'$ref': '#/$defs/category'}
                        },
                        'required': ['hemoptysis', 'severe_dyspnea', 'consciousness_change',
                                    'severe_chest_pain', 'high_fever', 'anaphylaxis_signs']
                    }
                },
                'required': ['categories'],
                '$defs': {
                    'category': {
                        'type': 'object',
                        'properties': {
                            'label': {'type': 'string'},
                            'severity': {'type': 'string', 'enum': ['high', 'medium']},
                            'action': {'type': 'string', 'enum': ['safety_alert', 'review_priority']},
                            'description': {'type': 'string'},
                            'patterns': {
                                'type': 'array',
                                'items': {'type': 'string'},
                                'minItems': 4,
                                'maxItems': 12
                            },
                            'false_positive_excludes': {
                                'type': 'array',
                                'items': {
                                    'type': 'object',
                                    'properties': {
                                        'if_pattern_matches': {'type': 'string'},
                                        'but_also_contains': {
                                            'type': 'array',
                                            'items': {'type': 'string'}
                                        }
                                    },
                                    'required': ['if_pattern_matches', 'but_also_contains']
                                }
                            }
                        },
                        'required': ['label', 'severity', 'action', 'description', 'patterns']
                    }
                }
            }
        }
    }
}


PROMPT = """당신은 한국 응급의학 가이드라인 전문가입니다.
호흡기 외래 환경에서 환자가 발화하면 즉시 의료진이 우선 평가해야 할 위험 키워드 사전을 생성하세요.

대상 환경: 이비인후과·호흡기내과 외래 (응급실 아님)
환자: 60-70대 어르신 (사투리·구어체 발화 빈번)

6개 카테고리:
  - hemoptysis (객혈 의증): 기도/폐 출혈
  - severe_dyspnea (심한 호흡곤란): 응급 산소 평가
  - consciousness_change (의식 변화): 신경학적 평가
  - severe_chest_pain (심한 흉통): 심혈관·기흉 감별
  - high_fever (고열): 패혈증 감별
  - anaphylaxis_signs (아나필락시스 의증): 응급 알레르기

각 카테고리에 대해:
1. label (한국어 표시명)
2. severity: 'high' (즉시 흐름 중단) 또는 'medium' (우선순위 상향)
3. action: 'safety_alert' (SafetyAlertScreen 분기) 또는 'review_priority' (의사 화면 amber 배지)
4. description: 왜 위험한가, 어떤 감별이 필요한가
5. patterns: 환자가 실제로 말할 법한 한국어 표현 4~12개 (사투리 포함)
6. false_positive_excludes: 패턴이 매칭되어도 함께 등장하면 제외할 단어들
   예: hemoptysis의 '피' 패턴은 '피곤', '피로', '피부', '피해'와 함께 있으면 제외

safety_keywords_set 도구를 호출하세요."""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='data/safety_keywords.json')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    if args.dry_run:
        print("[DRY RUN]")
        return

    bedrock = boto3.client('bedrock-runtime',
                          region_name=os.environ.get('AWS_REGION', 'ap-northeast-2'))

    print("=== 위험 키워드 사전 빌드 ===")
    response = bedrock.converse(
        modelId='anthropic.claude-3-5-sonnet-20241022-v2:0',
        messages=[{'role': 'user', 'content': [{'text': PROMPT}]}],
        toolConfig={
            'tools': [TOOL_SAFETY_KEYWORDS],
            'toolChoice': {'tool': {'name': 'safety_keywords_set'}}
        },
        inferenceConfig={'temperature': 0.3, 'maxTokens': 4096}
    )

    result = None
    for block in response['output']['message']['content']:
        if 'toolUse' in block:
            result = block['toolUse']['input']
            break

    if not result:
        print("✗ LLM 응답 없음")
        return

    # 메타 추가
    final = {
        '_meta': {
            'version': '2.0',
            'generated_by': 'build_safety_keywords.py + Claude Sonnet',
            'note': '응급의학 가이드라인 기반 LLM 자동 생성. 일반 개발자가 false positive 검증 권장.',
            'total_categories': len(result['categories']),
            'total_patterns': sum(len(c['patterns']) for c in result['categories'].values())
        },
        **result['categories']  # flat 구조로 저장
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(final, f, ensure_ascii=False, indent=2)

    print(f"✓ 저장: {output_path}")
    print(f"  카테고리: {final['_meta']['total_categories']}")
    print(f"  총 패턴: {final['_meta']['total_patterns']}")
    print(f"  예상 비용: 약 $0.05")


if __name__ == '__main__':
    main()
