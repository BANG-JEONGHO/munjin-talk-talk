# qwen_voice

Qwen Voice Clone 로컬 테스트 실행 파일을 모아둔 폴더입니다.

자세한 프로젝트 설명, 실행 순서, 데이터 관리 원칙은 repository root의 `README.md`를 확인하세요.

## 이 폴더의 역할

- Qwen TTS 환경 확인
- reference audio 기반 단건 생성 테스트
- 문진 대본 batch 생성 테스트
- 생성 결과 metadata 관리

## 주의

다음 파일과 폴더는 GitHub에 올리지 않습니다.

- `data/`
- `outputs/`
- reference audio
- generated wav
- model weight
- `.env`
