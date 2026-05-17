# qwen_voice/config.py

MODEL_ID = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"

# Local GTX 1650Ti Max-Q 기준
# flash_attention_2보다 eager가 안전한 출발점
ATTN_IMPLEMENTATION = "eager"
BATCH_SIZE = 1

DATA_DIR = "qwen_voice/data"
REFERENCE_DIR = "qwen_voice/data/reference_audio"
OUTPUT_DIR = "qwen_voice/outputs"
