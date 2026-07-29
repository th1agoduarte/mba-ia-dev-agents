import os
from dotenv import load_dotenv

load_dotenv()

REFUND_APPROVAL_THRESHOLD = float(
    os.environ.get("REFUND_APPROVAL_THRESHOLD", "50"))

REFUND_MAX_LIMIT = float(os.environ.get("REFUND_MAX_LIMIT", "200"))