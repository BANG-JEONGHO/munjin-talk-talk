# 문진톡톡 Qwen Voice Clone Local Pipeline

> Branch: `qwen-tts`  
> Purpose: Qwen Clone 모델을 활용한 문진 합성 발화 데이터 생성 파이프라인 테스트

## 1. 프로젝트 맥락

문진톡톡은 고령 환자가 진료 전에 평소 말투로 증상, 걱정, 의사에게 묻고 싶은 점을 말하면 그 내용을 의료진이 확인할 수 있는 문진 원페이퍼로 정리하는 AI 문진 서비스입니다.

이 브랜치는 문진톡톡 서비스 본체 개발 브랜치가 아니라, **Qwen Clone / Qwen TTS 기반 합성 문진 발화 데이터 생성 환경을 테스트하기 위한 브랜치**입니다.

핵심 목표는 다음과 같습니다.

- AI Hub 강원권·고령층 발화 데이터를 reference voice로 활용
- 문진톡톡 서비스에 필요한 합성 문진 발화 샘플 생성
- 로컬 환경에서 Qwen voice clone 구동 가능 여부 확인
- 이후 GPU 서버에서 batch 생성 파이프라인으로 확장

## 2. 이 브랜치의 목표

현재 `qwen-tts` 브랜치에서는 다음을 검증합니다.

1. 로컬 conda 환경에서 Qwen TTS 패키지가 정상 동작하는지 확인
2. 로컬 환경에서 최소 1개 샘플 생성 가능 여부 확인
3. `attn_implementation="eager"` 설정으로 안정 실행 가능한지 확인
4. reference audio와 대본 CSV를 이용한 단건 생성 구조 확인
5. 이후 여러 대본을 batch로 생성할 수 있는 구조로 확장


## 3. 폴더 구조

현재 구조는 최대한 단순하게 유지합니다.

~~~text
munjin-talk-talk/
  README.md
  .gitignore
  qwen_voice/
    README.md
    requirements.txt
    config.py
    check_env.py
    scripts.example.csv
    speakers.example.csv
~~~

로컬에서만 존재하는 폴더는 다음과 같습니다.

~~~text
qwen_voice/data/
  reference_audio/
    spk001_ref.wav
  scripts.csv
  speakers.csv

qwen_voice/outputs/
  generated wav files
~~~

## 4. 로컬 환경 세팅

기존의 conda 환경이 있다면 우선 그대로 사용합니다.

~~~bash
conda activate <기존 Qwen 환경 이름>
pip install -r qwen_voice/requirements.txt
python qwen_voice/check_env.py
~~~

정상이라면 마지막에 다음과 유사한 출력이 나와야 합니다.

~~~text
cuda available: True
gpu: NVIDIA GeForce GTX XXXX ...
Qwen3TTSModel import: OK
~~~

`attn_implementation="eager"`는 모델 로드 시 사용하는 attention 구현 방식입니다.
기존의 설정에서 수정해주셔야 로컬에서 작동하기 편리합니다.

## 5. 현재 설정

`qwen_voice/config.py`에서 기본 설정을 관리합니다.

~~~python
MODEL_ID = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
ATTN_IMPLEMENTATION = "eager"
BATCH_SIZE = 1
DATA_DIR = "qwen_voice/data"
REFERENCE_DIR = "qwen_voice/data/reference_audio"
OUTPUT_DIR = "qwen_voice/outputs"
~~~

로컬 환경에서는 우선 `eager`로 안정성을 확인합니다.  
클라우드 GPU 환경으로 넘어간 뒤 `sdpa` 또는 `flash_attention_2`를 비교합니다.

## 6. 데이터 파일 형식

### scripts.csv

생성할 문진 대본 목록 예시입니다.

~~~csv
sample_id,text,ref_speaker_id
sample_001,"어제부터 가심이 답답하고 숨이 좀 차요. 밤에 더 그래요.",spk001
sample_002,"기침이 며칠째 나고 가래도 있어요. 약을 계속 먹어야 하는지 물어보고 싶어요.",spk001
~~~

### speakers.csv

reference voice 정보입니다.

~~~csv
ref_speaker_id,ref_audio,ref_text
spk001,qwen_voice/data/reference_audio/spk001_ref.wav,"참조 음성의 정확한 전사문"
~~~


## 7. 작업 순서

### Step 1. 환경 확인

~~~bash
conda activate <기존 Qwen 환경 이름>
python qwen_voice/check_env.py
~~~

### Step 2. 단건 생성 테스트

추후 `generate_one.py`를 추가하여 다음을 검증합니다.

- 모델 로드
- reference audio 입력
- reference text 입력
- 문진 대본 1개 합성
- wav 파일 저장

### Step 3. batch 생성 테스트

추후 `generate_batch.py`를 추가하여 다음을 검증합니다.

- scripts.csv 읽기
- speakers.csv 읽기
- speaker별 reference prompt 재사용
- 여러 문진 대본 순차 생성
- outputs 폴더에 wav 저장
- metadata 저장

## 8. 합성 데이터 설계 원칙

문진톡톡의 합성 데이터는 단순 음성 파일이 아니라, 문진 서비스 검증용 데이터로 관리합니다.

1개 샘플은 다음 요소를 포함해야 합니다.

- 문진 대본
- reference speaker 정보
- 생성된 음성 파일
- 표준 증상 후보
- 환자 질문
- 의사 확인 항목
- 생성 조건 metadata

예상 metadata 구조는 다음과 같습니다.

~~~json
{
  "sample_id": "sample_001",
  "text": "어제부터 가심이 답답하고 숨이 좀 차요. 밤에 더 그래요.",
  "ref_speaker_id": "spk001",
  "symptom_candidates": ["흉부 답답함", "호흡곤란", "야간 악화"],
  "patient_questions": ["복약 지속 여부 질문"],
  "doctor_check_items": ["시작 시점", "호흡곤란 정도", "복용약명"],
  "model": "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
  "synthetic": true
}
~~~

## 9. 안전 원칙

이 브랜치의 결과물은 개발·검증용 합성 데이터입니다.

다음 원칙을 지킵니다.

- 실제 환자 음성은 사용하지 않는다.
- 실제 환자 문진 원문은 저장하지 않는다.
- AI Hub 데이터 이용 조건을 확인한다.
- 원본 음성 파일은 GitHub에 올리지 않는다.
- 생성된 wav 파일도 GitHub에 올리지 않는다.
- 합성 데이터에는 synthetic 표시를 남긴다.
- AI가 의료 판단을 하는 것처럼 보이는 대본은 제외한다.
