"""Stage only reviewed public files for APIMatic; never copy the repository."""
import shutil
from pathlib import Path

from export_candidate_openapi import DESTINATION, ROOT, rendered_specification


def main() -> None:
    assert DESTINATION.read_text(encoding="utf-8") == rendered_specification(), "Regenerate the candidate contract first"
    target = ROOT / "tmp/phase10-apimatic-input/src"
    source = ROOT / "docs/apimatic/src"
    allowed = ("APIMATIC-BUILD.json", "content/toc.yml", "content/guides/overview.md")
    expected = {Path(name) for name in allowed} | {Path("spec/candidate-agent.openapi.json")}
    if target.exists():
        actual = {p.relative_to(target) for p in target.rglob("*") if p.is_file()}
        assert actual <= expected, "Unexpected files in staging; use a clean reviewed staging directory"
    for name in allowed:
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, destination)
    (target / "spec").mkdir(exist_ok=True)
    shutil.copyfile(DESTINATION, target / "spec/candidate-agent.openapi.json")
    print("Staged exactly four public files in tmp/phase10-apimatic-input/src")


if __name__ == "__main__":
    main()
