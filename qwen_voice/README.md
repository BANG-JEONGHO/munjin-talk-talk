# Qwen Voice Clone Local Test

문진톡톡 합성 문진 발화 데이터 생성을 위한 Qwen Clone 로컬 테스트 폴더입니다.

## 목적

- AI Hub 강원권/고령층 발화 데이터를 reference voice로 활용
- 문진톡톡 서비스용 합성 문진 발화 샘플 생성
- 로컬 환경에서 먼저 1개 생성 테스트
- 이후 GPU 서버에서 batch 생성으로 확장

## 현재 로컬 기준

- attn_implementation: eager
- batch size: 1
- 실제 음성 데이터와 생성 결과물은 GitHub에 업로드하지 않음

## GitHub에 올리지 않는 것

- AI Hub 원본 데이터
- reference audio
- 생성된 wav 파일
- 모델 weight
- outputs
- .env

## 실행 순서

1. 기존 conda 환경 활성화
2. requirements 설치
3. 환경 확인 스크립트 실행

명령어:

conda activate <기존 Qwen 환경 이름>
pip install -r qwen_voice/requirements.txt
python qwen_voice/check_env.py
