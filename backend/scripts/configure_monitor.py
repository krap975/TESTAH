"""Create a separate local monitoring credential without printing it or changing other settings."""
from pathlib import Path
import re
import secrets


def main() -> None:
    path = Path(__file__).resolve().parents[1] / ".env"
    if not path.exists():
        raise SystemExit("backend/.env is missing. Follow README setup first.")
    original = path.read_bytes()
    text = original.decode("utf-8")
    lines = text.splitlines(keepends=True)
    matching = [index for index, line in enumerate(lines) if re.match(r"\s*(?:export\s+)?TESTAH_MONITOR_TOKEN\s*=", line)]
    if len(matching) > 1:
        raise SystemExit("Duplicate monitoring settings found. Resolve them locally before configuring monitoring.")
    if matching and lines[matching[0]].split("=", 1)[1].strip() not in {"", "''", '""'}:
        print("Existing monitoring token preserved in backend/.env. Restart the API after configuration changes.")
        return
    ending = "\r\n" if b"\r\n" in original else "\n"
    setting = "TESTAH_MONITOR_TOKEN=" + secrets.token_urlsafe(32) + ending
    if matching:
        lines[matching[0]] = setting
        updated = "".join(lines).encode("utf-8")
    else:
        updated = original + (b"" if original.endswith(b"\n") else ending.encode()) + setting.encode("utf-8")
    path.write_bytes(updated)
    print("Separate monitoring token configured in backend/.env; value not printed. Copy it locally into the monitor access field and restart the API.")


if __name__ == "__main__":
    main()
