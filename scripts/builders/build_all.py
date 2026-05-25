"""
build_all.py
─────────────
모든 의료 도메인 데이터를 한 번에 자동 생성하는 통합 빌드 러너.

실행 순서:
  1. build_slot_cards.py        (87 슬롯 정의·예시, 약 $0.30)
  2. build_review_templates.py  (의료진 확인 항목, 약 $0.50)
  3. build_safety_keywords.py   (위험 키워드 사전, 약 $0.05)
  4. build_forbidden_outputs.py (금지 출력 패턴, 약 $0.05)

총 비용: 약 $1
총 시간: 약 1.2시간
필요 권한: Bedrock Claude Sonnet 액세스 (ap-northeast-2)

사용법:
  python scripts/builders/build_all.py
  python scripts/builders/build_all.py --skip slots         # 슬롯 빌드 스킵
  python scripts/builders/build_all.py --dry-run            # LLM 호출 없이 흐름만 확인
"""

import sys
import time
import argparse
import subprocess
from pathlib import Path

SCRIPTS = [
    ('slots',       'build_slot_cards.py',         '슬롯 카드 정의·예시'),
    ('reviews',     'build_review_templates.py',   '의료진 확인 항목'),
    ('safety',      'build_safety_keywords.py',    '위험 키워드 사전'),
    ('forbidden',   'build_forbidden_outputs.py',  '금지 출력 패턴'),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--skip', nargs='*', default=[], help='스킵할 빌드 (slots/reviews/safety/forbidden)')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    print("=" * 60)
    print("문진톡톡 의료 도메인 데이터 빌드 (4개 스크립트 통합)")
    print("=" * 60)
    print()

    builders_dir = Path(__file__).parent
    start_time = time.time()
    successes = 0

    for key, script, desc in SCRIPTS:
        if key in args.skip:
            print(f"[SKIP] {script} ({desc})")
            continue

        print(f"\n[{key.upper()}] {script} — {desc}")
        print("-" * 60)

        cmd = [sys.executable, str(builders_dir / script)]
        if args.dry_run:
            cmd.append('--dry-run')

        result = subprocess.run(cmd)
        if result.returncode == 0:
            successes += 1
            print(f"✓ {script} 완료")
        else:
            print(f"✗ {script} 실패 (returncode={result.returncode})")
            print("  중단 여부 결정: 다음 단계는 의존성 있을 수 있음")

    elapsed = time.time() - start_time
    print()
    print("=" * 60)
    print(f"전체 완료: {successes}/{len(SCRIPTS) - len(args.skip)}개 성공")
    print(f"소요 시간: {elapsed/60:.1f}분")
    if not args.dry_run and successes == len(SCRIPTS) - len(args.skip):
        print(f"예상 누적 비용: 약 $1.00")
    print("=" * 60)


if __name__ == '__main__':
    main()
