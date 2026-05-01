from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import urlparse


ASSET_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".svg",
    ".ico",
    ".pdf",
    ".zip",
    ".xml",
    ".css",
    ".js",
    ".json",
    ".woff",
    ".woff2",
    ".ttf",
}


@dataclass(frozen=True)
class DiscoveryUrlPolicy:
    blocked_path_tokens: tuple[str, ...]
    max_candidates: int


@dataclass(frozen=True)
class DiscoveryFilterResult:
    accepted_urls: list[str]
    rejected_urls: list[str]


def build_discovery_url_policy(
    *,
    blocked_path_tokens_csv: str,
    max_candidates: int,
) -> DiscoveryUrlPolicy:
    blocked_tokens = tuple(
        token.strip().lower()
        for token in blocked_path_tokens_csv.split(",")
        if token.strip()
    )
    return DiscoveryUrlPolicy(
        blocked_path_tokens=blocked_tokens,
        max_candidates=max(1, max_candidates),
    )


def apply_discovery_url_policy(
    candidate_urls: list[str],
    policy: DiscoveryUrlPolicy,
) -> DiscoveryFilterResult:
    accepted: list[str] = []
    rejected: list[str] = []

    for url in candidate_urls:
        if len(accepted) >= policy.max_candidates:
            rejected.append(url)
            continue
        if not _is_candidate_url_allowed(url, policy.blocked_path_tokens):
            rejected.append(url)
            continue
        accepted.append(url)

    return DiscoveryFilterResult(accepted_urls=accepted, rejected_urls=rejected)


def _is_candidate_url_allowed(url: str, blocked_path_tokens: tuple[str, ...]) -> bool:
    parsed = urlparse(url)
    path = (parsed.path or "/").lower()

    suffix = PurePosixPath(path).suffix.lower()
    if suffix in ASSET_EXTENSIONS:
        return False

    # Guardrail against low-value fan-out in taxonomy/system pages.
    for token in blocked_path_tokens:
        if not token:
            continue
        if f"/{token}/" in path or path.endswith(f"/{token}") or path.startswith(f"/{token}/"):
            return False

    return True
