"""Export the deterministic FastAPI contract consumed by the web client."""

import json
import os
from pathlib import Path

os.environ.setdefault("FIDO_ENVIRONMENT", "test")
os.environ.setdefault("FIDO_PROVIDER_MODE", "test")

from app.main import app


def main() -> None:
    target = Path(__file__).resolve().parents[1] / "openapi.json"
    target.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
