import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

LITELLM_BASE_URL = os.getenv("LITELLM_BASE_URL", "http://127.0.0.1:4000/v1")
LITELLM_API_KEY = os.getenv("LITELLM_API_KEY", "sk-noop")
LPA_MODEL = os.getenv("LPA_MODEL", "qwen3.5-35b")
KB_DIR = Path(os.getenv("KB_DIR", str(Path(__file__).resolve().parents[2] / "backend" / "kb"))).resolve()
MAX_TOOL_ITERATIONS = int(os.getenv("MAX_TOOL_ITERATIONS", "8"))
REQUEST_TIMEOUT_S = float(os.getenv("REQUEST_TIMEOUT_S", "120"))
