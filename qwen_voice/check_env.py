# qwen_voice/check_env.py

import sys

print("python:", sys.version)

try:
    import torch
    print("torch:", torch.__version__)
    print("cuda available:", torch.cuda.is_available())

    if torch.cuda.is_available():
        print("gpu:", torch.cuda.get_device_name(0))
        print("cuda version:", torch.version.cuda)
except Exception as e:
    print("torch import: FAILED")
    print(repr(e))

try:
    import qwen_tts
    print("qwen_tts package path:", getattr(qwen_tts, "__file__", "unknown"))

    from qwen_tts import Qwen3TTSModel
    print("Qwen3TTSModel import: OK")
except Exception as e:
    print("qwen_tts import: FAILED")
    print(repr(e))
