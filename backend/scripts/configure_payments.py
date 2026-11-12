"""Create a separate local payment operator token; never print it or change payment mode."""
from pathlib import Path
import re
import secrets


def main() -> None:
    path = Path(__file__).resolve().parents[1] / ".env"
    if not path.exists():
        raise SystemExit("backend/.env is missing. Follow README setup first.")
    original = path.read_bytes()
    lines = original.decode("utf-8").splitlines(keepends=True)
    matches = [i for i, line in enumerate(lines) if re.match(r"\s*(?:export\s+)?TESTAH_PAYMENT_OPERATOR_TOKEN\s*=", line)]
    if len(matches) > 1:
        raise SystemExit("Duplicate payment operator settings found. Resolve them locally first.")
    if matches and lines[matches[0]].split("=", 1)[1].strip() not in {"", "''", '""'}:
        print("Existing payment operator token preserved in backend/.env. Value not printed.")
        return
    ending = "\r\n" if b"\r\n" in original else "\n"
    setting = "TESTAH_PAYMENT_OPERATOR_TOKEN=" + secrets.token_urlsafe(32) + ending
    if matches:
        lines[matches[0]] = setting
        updated = "".join(lines).encode("utf-8")
    else:
        updated = original + (b"" if original.endswith(b"\n") else ending.encode()) + setting.encode()
    path.write_bytes(updated)
    print("Separate payment operator token configured in backend/.env; value not printed. Copy it locally into the Sandbox checkout panel and restart the API.")


if __name__ == "__main__":
    main()
