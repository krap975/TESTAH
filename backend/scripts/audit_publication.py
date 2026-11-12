"""Read-only public-file/known-secret audit. Prints paths/rule names, never values.

Run from any directory after git init. Includes staged and nonignored source.
This complements a pattern scanner (e.g. gitleaks); it is not proof of no secrets.
"""
import argparse
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit
import zipfile

ROOT = Path(__file__).resolve().parents[2]


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", "-c", f"safe.directory={ROOT.as_posix()}", "-C", str(ROOT), *args],
                                   stderr=subprocess.DEVNULL)


def known_secrets() -> set[bytes]:
    values = set()
    entries = list(os.environ.items())
    # Read local secrets only in memory for exact-match detection. Never print them.
    for directory in (ROOT / "backend", ROOT / "frontend", ROOT / "sample_agents", ROOT):
        for path in directory.glob(".env*"):
            if path.name.endswith(".example") or not path.is_file():
                continue
            for line in path.read_text(encoding="utf-8-sig").splitlines():
                if "=" in line and not line.lstrip().startswith("#"):
                    key, value = line.split("=", 1)
                    entries.append((key.strip(), value.strip().strip("\"'")))
    for key, value in entries:
        if key == "TESTAH_AGENT_SECRETS":
            try:
                for secret in json.loads(value).values():
                    if isinstance(secret, str):
                        values.add(secret.encode())
                        if secret.startswith("Bearer "):
                            values.add(secret[7:].encode())
            except (ValueError, AttributeError):
                pass
        elif key.endswith("DATABASE_URL"):
            try:
                password = urlsplit(value).password
                if password:
                    values.add(unquote(password).encode())
            except ValueError:
                pass
        elif key.startswith(("TESTAH_", "VITE_", "GEMINI_", "GOOGLE_", "PAYPAL_")) and any(
            word in key for word in ("TOKEN", "SECRET", "API_KEY", "CLIENT_ID")
        ):
            values.add(value.encode())
    return {value for value in values if len(value) >= 12 and value.lower() not in {
        b"your-api-key", b"your-client-id", b"your-client-secret",
    } and not value.lower().startswith((b"replace", b"your_", b"placeholder"))}


PATTERNS = {
    "google-api-key": re.compile(rb"AIza[0-9A-Za-z_-]{35}"),
    "github-token": re.compile(rb"(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,})"),
    "openai-key": re.compile(rb"sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}"),
    "private-key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "aws-access-key": re.compile(rb"(?:AKIA|ASIA)[0-9A-Z]{16}"),
    "credential-url": re.compile(rb"(?:postgres(?:ql)?|mysql)://[^\s:/]+:[^\s@/]{12,}@"),
}


def private_path(name: str) -> bool:
    path = Path(name)
    return (any(part in {".venv", "node_modules", "__pycache__", "tmp", ".aws", ".codex", ".agents"} for part in path.parts)
            or (path.name.startswith(".env") and path.name != ".env.example")
            or path.suffix.lower() in {".db", ".sqlite", ".sqlite3", ".log", ".pem", ".key", ".p12", ".pfx", ".dump", ".bak"})


def scan_bytes(name: str, data: bytes, secrets: set[bytes], findings: list[dict], depth: int = 0) -> None:
    if any(secret in data for secret in secrets):
        findings.append({"path": name, "rule": "configured-local-secret"})
    for rule, pattern in PATTERNS.items():
        if pattern.search(data):
            findings.append({"path": name, "rule": rule})
    if depth < 2 and data.startswith(b"PK"):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for info in archive.infolist():
                if info.file_size > 20_000_000:
                    findings.append({"path": name, "rule": "archive-member-needs-review"})
                elif not info.is_dir():
                    scan_bytes(name + "::" + info.filename, archive.read(info), secrets, findings, depth + 1)


def audit(include_history: bool = False) -> dict:
    names = sorted(set(git("ls-files", "--cached", "--others", "--exclude-standard", "-z").decode().split("\0")) - {""})
    secrets = known_secrets()
    findings = []
    for name in names:
        path = ROOT / name
        if private_path(name):
            findings.append({"path": name, "rule": "private-runtime-file-in-public-set"})
        if path.is_file():
            scan_bytes(name, path.read_bytes(), secrets, findings)
    # Verify the ignored production bundle too: VITE_ substitution must not leak keys.
    bundle_files = list((ROOT / "frontend/dist").rglob("*"))
    for path in bundle_files:
        if path.is_file():
            scan_bytes(path.relative_to(ROOT).as_posix(), path.read_bytes(), secrets, findings)
    commits = git("rev-list", "--all").decode().splitlines()
    blobs = 0
    if include_history:
        for entry in git("rev-list", "--objects", "--all").decode().splitlines():
            object_id, _, name = entry.partition(" ")
            if git("cat-file", "-t", object_id).strip() == b"blob":
                blobs += 1
                scan_bytes("history:" + name, git("cat-file", "blob", object_id), secrets, findings)
    return {"public_files": len(names), "built_files_scanned": sum(p.is_file() for p in bundle_files),
            "local_secret_values_checked": len(secrets), "reachable_commits": len(commits),
            "history_blobs_scanned": blobs, "findings": findings}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", action="store_true")
    args = parser.parse_args()
    result = audit(args.history)
    print(json.dumps(result, indent=2))
    sys.exit(bool(result["findings"]))
