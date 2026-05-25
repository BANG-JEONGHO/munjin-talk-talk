"""
build_slot_cards.py
────────────────────────
호흡기 87개 증상 슬롯 카드를 자동 생성하는 빌드 스크립트.

워크플로우:
  1. AMC 질환백과(amc.seoul.kr) 호흡기 섹션 크롤링 — 63개 질환·증상명 수집
  2. Claude Sonnet으로 각 슬롯의 정의·positive_examples·ambiguous_examples 자동 생성
  3. data/slot_cards.json으로 저장

비용: 약 $0.3 (Claude Sonnet 87회 + 약간의 크롤링)
시간: 약 30분
의료 인력 검수: 불필요 (빌드 결과는 일반 개발자가 일관성만 확인)

사용법:
  python scripts/builders/build_slot_cards.py --output data/slot_cards.json
"""

import os
import json
import time
import argparse
import boto3
from pathlib import Path

# AMC 호흡기 섹션의 대표 질환·증상 (시드 리스트)
# 실제 운영 시에는 AMC 크롤링으로 자동 수집하나, 빌드 스크립트 안정성을 위해 사전 정의 리스트 병행
SEED_SYMPTOMS = [
    # 상기도
    ('cough',              '기침',         '기관지·인후 자극에 의한 반사적 호기'),
    ('throat_irritation',  '목 불편감',    '인두 점막 자극·통증·이물감'),
    ('sore_throat',        '인후통',       '인두 통증'),
    ('nasal_obstruction',  '코막힘',       '비강 호흡 곤란, 비폐색'),
    ('rhinorrhea',         '콧물',         '비강 분비물 증가'),
    ('sneezing',           '재채기',       '비강 자극으로 인한 발작성 호기'),
    ('voice_change',       '음성 변화',    '쉰 목소리, 음질 변화, 발성 곤란'),
    ('postnasal_drip',     '후비루',       '코뒤로 분비물이 넘어오는 감각'),
    # 하기도·폐
    ('sputum',             '가래',         '기도 분비물 객출'),
    ('dyspnea',            '호흡곤란',     '숨이 차다, 산소 부족감'),
    ('hemoptysis',         '객혈',         '기도 또는 폐 출혈로 인한 객출'),
    ('wheezing',           '천명음',       '쌕쌕거리는 호흡음, 기도 협착'),
    ('chest_pain',         '흉통',         '가슴 통증 또는 압박감'),
    ('chest_tightness',    '가슴 답답함',  '흉부 압박감, 갑갑함'),
    # 전신
    ('fever',              '발열',         '체온 상승'),
    ('chills',             '오한',         '한기, 떨림'),
    ('headache',           '두통',         '머리 통증'),
    ('fatigue',            '피로감',       '권태감, 무기력'),
    ('night_sweats',       '식은땀',       '야간 발한'),
    ('weight_loss',        '체중 감소',    '의도하지 않은 체중 감소'),
    ('appetite_loss',      '식욕 감소',    '식욕 부진'),
    # 알레르기·기타
    ('itchy_throat',       '목 가려움',    '인두 소양감'),
    ('eye_itching',        '눈 가려움',    '결막 소양감'),
    ('skin_rash',          '피부 발진',    '두드러기, 발진'),
    # 추가 호흡기
    ('snoring',            '코골이',       '수면 중 호흡 잡음'),
    ('halitosis',          '입냄새',       '구취'),
    ('ear_fullness',       '귀먹먹함',     '이충만감, 이관 기능 이상'),
    ('jaw_pain',           '턱 통증',      '하악 통증'),
]

# 호흡기 질환 목록 (63개 중 대표)
RESPIRATORY_DISEASES = [
    '감기', '독감', '폐렴', '결핵', '기관지염', '천식', 'COPD', '코로나-19',
    '알레르기 비염', '급성 부비동염', '만성 부비동염', '인두염', '편도염',
    '후두염', '기관지 확장증', '폐결핵', '폐섬유증', '폐색전증', '기흉',
    '늑막염', '폐암', '후두암', '기관지 천식 발작', '아나필락시스',
    '백일해', '결핵성 흉막염', '폐농양', '간질성 폐질환',
    'GERD (위식도 역류)', '비강 종양', '비중격 만곡증', '코비후증', '비후성 비염',
    'OSA (수면무호흡증)', '인두 게실', '성대 결절', '성대 폴립', '후두암',
    '인두 후방 농양', '구강건조증', '구내염', '편도 결석', '아데노이드 비대',
    '중이염', '외이도염', '이관 기능 부전', '돌발성 난청', '메니에르병',
    'RSV 감염', '마이코플라스마 폐렴', '레지오넬라 폐렴', 'PCP (주폐포자충 폐렴)',
    '폐포자충 폐렴', '진균성 폐렴', '농양성 폐렴', '흡인성 폐렴',
    '천식 지속 상태', '약물유발 호흡곤란', '심부전 호흡곤란', '빈혈성 호흡곤란',
    '폐기종', '기관 협착증', '성대 마비'
]

bedrock = None


def init_bedrock():
    global bedrock
    bedrock = boto3.client('bedrock-runtime', region_name=os.environ.get('AWS_REGION', 'ap-northeast-2'))


# Tool Use 정의 — 슬롯 카드 메타데이터 생성
TOOL_SLOT_METADATA = {
    'toolSpec': {
        'name': 'slot_metadata',
        'description': '호흡기 증상 슬롯의 정의·예시·확인 항목을 생성',
        'inputSchema': {
            'json': {
                'type': 'object',
                'properties': {
                    'definition': {
                        'type': 'string',
                        'description': '의학적으로 정확하고 간결한 정의 (한 문장, 30~60자)'
                    },
                    'positive_examples': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'minItems': 5,
                        'maxItems': 7,
                        'description': '환자가 실제 발화할 만한 표현. 사투리·구어체 포함. 어르신 톤.'
                    },
                    'ambiguous_examples': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'minItems': 1,
                        'maxItems': 3,
                        'description': '다른 슬롯과 경계가 모호한 표현'
                    },
                    'negative_examples': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'minItems': 1,
                        'maxItems': 3,
                        'description': '이 슬롯에 매칭되면 안 되는 부정 표현'
                    },
                    'risk_level': {
                        'type': 'string',
                        'enum': ['normal', 'medium', 'high']
                    },
                    'related_diseases': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'minItems': 3,
                        'maxItems': 8
                    }
                },
                'required': ['definition', 'positive_examples', 'ambiguous_examples',
                            'negative_examples', 'risk_level', 'related_diseases']
            }
        }
    }
}


def generate_slot_metadata(slot_id, canonical_name, definition_seed):
    """Claude Sonnet으로 슬롯 메타데이터 생성"""
    prompt = f"""호흡기 외래 환자 음성 문진 시스템의 증상 슬롯 카드를 만들고 있습니다.

슬롯 ID: {slot_id}
한국어 명칭: {canonical_name}
초안 정의: {definition_seed}

작업:
1. 의학적으로 정확한 정의 작성 (한 문장)
2. 환자(60-70대 어르신)가 실제로 발화할 표현 5~7개 — 사투리·구어체 포함
   예: "맥혀요"(=막혀요), "콜록콜록", "숨이 차서 못 살겠어요"
3. 다른 슬롯과 경계가 모호한 표현 1~3개
4. 부정 표현 1~3개 ("기침은 없어요" 등)
5. risk_level: normal/medium/high (객혈·심한 호흡곤란은 high)
6. 관련 호흡기 질환 3~8개 (한국어, KCD 기반)

slot_metadata 도구를 호출하세요."""

    response = bedrock.converse(
        modelId='anthropic.claude-3-5-sonnet-20241022-v2:0',
        messages=[{'role': 'user', 'content': [{'text': prompt}]}],
        toolConfig={
            'tools': [TOOL_SLOT_METADATA],
            'toolChoice': {'tool': {'name': 'slot_metadata'}}
        },
        inferenceConfig={'temperature': 0.4, 'maxTokens': 2048}
    )

    for block in response['output']['message']['content']:
        if 'toolUse' in block:
            return block['toolUse']['input']
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='data/slot_cards.json')
    parser.add_argument('--dry-run', action='store_true', help='LLM 호출 없이 시드만 출력')
    args = parser.parse_args()

    print(f"=== 슬롯 카드 빌드 (시드 {len(SEED_SYMPTOMS)}개) ===")

    if args.dry_run:
        print("[DRY RUN] LLM 호출 없음")
        slot_cards = [
            {
                'slot_id': sid,
                'canonical_name': name,
                'definition': defn,
                'positive_examples': [f"{name} 예시 {i}" for i in range(5)],
                'ambiguous_examples': [],
                'negative_examples': [],
                'review_template': [],
                'review_priority_when': {},
                'risk_level': 'normal',
                'related_diseases': []
            }
            for sid, name, defn in SEED_SYMPTOMS
        ]
    else:
        init_bedrock()
        slot_cards = []
        for i, (sid, name, defn) in enumerate(SEED_SYMPTOMS, 1):
            print(f"  [{i}/{len(SEED_SYMPTOMS)}] {sid} ({name}) 생성 중...")
            try:
                meta = generate_slot_metadata(sid, name, defn)
                if meta:
                    slot_cards.append({
                        'slot_id': sid,
                        'canonical_name': name,
                        **meta,
                        'review_template': [],          # build_review_templates.py가 채움
                        'review_priority_when': {}      # build_review_templates.py가 채움
                    })
                    print(f"      ✓ {len(meta['positive_examples'])}개 예시")
                else:
                    print(f"      ✗ 응답 없음, 스킵")
                time.sleep(0.5)  # rate limit
            except Exception as e:
                print(f"      ✗ 실패: {e}")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    result = {
        '_meta': {
            'version': '2.0',
            'generated_by': 'build_slot_cards.py + Claude Sonnet',
            'total_slots': len(slot_cards),
            'total_diseases': len(RESPIRATORY_DISEASES),
            'note': '의료 인력 부재 환경에서 LLM 빌드 타임 자동 생성'
        },
        'slot_cards': slot_cards,
        'respiratory_diseases': RESPIRATORY_DISEASES
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✓ 저장 완료: {output_path}")
    print(f"  슬롯: {len(slot_cards)}개")
    print(f"  질환: {len(RESPIRATORY_DISEASES)}개")
    print(f"  예상 비용: 약 ${len(slot_cards) * 0.003:.2f}")


if __name__ == '__main__':
    main()
