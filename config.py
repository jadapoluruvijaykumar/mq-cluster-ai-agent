import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
MQSC_OUTPUT_DIR = OUTPUT_DIR / "mqsc"
DOCKER_OUTPUT_DIR = OUTPUT_DIR / "docker"

# Ensure output directories exist
MQSC_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DOCKER_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
DEFAULT_LLM_PROVIDER = os.getenv("DEFAULT_LLM_PROVIDER", "auto")

# IBM MQ Defaults
MQ_ADMIN_USER = os.getenv("MQ_ADMIN_USER", "admin")
MQ_ADMIN_PASSWORD = os.getenv("MQ_ADMIN_PASSWORD", "pass")
MQ_HTTP_VERIFY_SSL = os.getenv("MQ_HTTP_VERIFY_SSL", "false").lower() == "true"
MQ_DEFAULT_PORT = int(os.getenv("MQ_DEFAULT_PORT", "1414"))
MQ_REST_DEFAULT_PORT = int(os.getenv("MQ_REST_DEFAULT_PORT", "9443"))
MQ_DOCKER_IMAGE = os.getenv("MQ_DOCKER_IMAGE", "icr.io/ibm-com/mq:latest")

