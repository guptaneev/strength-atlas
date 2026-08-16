from __future__ import annotations

from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[1]
LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def test_public_docs_have_no_local_absolute_paths() -> None:
    files = [REPO_ROOT / "README.md", *sorted((REPO_ROOT / "docs").rglob("*.md"))]
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "/Users/" not in text, f"local macOS path in {path.relative_to(REPO_ROOT)}"
        assert not re.search(r"[A-Za-z]:\\\\", text), f"local Windows path in {path.relative_to(REPO_ROOT)}"


def test_local_markdown_links_resolve() -> None:
    files = [REPO_ROOT / "README.md", *sorted((REPO_ROOT / "docs").rglob("*.md"))]
    missing: list[str] = []
    for path in files:
        for raw_target in LINK_PATTERN.findall(path.read_text(encoding="utf-8")):
            target = raw_target.strip().strip("<>").split("#", 1)[0]
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.exists():
                missing.append(f"{path.relative_to(REPO_ROOT)} -> {raw_target}")
    assert not missing, "missing local documentation links:\n" + "\n".join(missing)
