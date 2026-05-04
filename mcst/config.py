"""환경설정 및 시드 로딩."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SEED_FILE = DATA_DIR / "gov_orgs.yaml"

load_dotenv(ROOT / ".env", override=False)

CATEGORY_LABELS = {
    "ministries": "부",
    "offices": "처",
    "agencies": "청",
    "commissions": "위원회",
}
PLATFORMS = ("youtube", "instagram", "x", "facebook", "blog")


@dataclass(frozen=True)
class Settings:
    youtube_api_key: str = ""
    meta_graph_token: str = ""
    x_bearer_token: str = ""
    naver_client_id: str = ""
    naver_client_secret: str = ""
    db_path: Path = DATA_DIR / "snapshots.sqlite"
    request_timeout: int = 15
    user_agent: str = "MCST-SNS-Analyzer/0.1"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            youtube_api_key=os.getenv("YOUTUBE_API_KEY", ""),
            meta_graph_token=os.getenv("META_GRAPH_TOKEN", ""),
            x_bearer_token=os.getenv("X_BEARER_TOKEN", ""),
            naver_client_id=os.getenv("NAVER_API_CLIENT_ID", ""),
            naver_client_secret=os.getenv("NAVER_API_CLIENT_SECRET", ""),
            db_path=Path(os.getenv("MCST_DB_PATH", str(DATA_DIR / "snapshots.sqlite"))),
            request_timeout=int(os.getenv("MCST_REQUEST_TIMEOUT", "15")),
            user_agent=os.getenv("MCST_USER_AGENT", "MCST-SNS-Analyzer/0.1"),
        )


def load_orgs(path: Path | None = None) -> list[dict[str, Any]]:
    """시드 YAML을 평탄화된 기관 리스트로 반환."""
    path = path or SEED_FILE
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    flat: list[dict[str, Any]] = []
    for category, entries in raw.items():
        for entry in entries or []:
            org = dict(entry)
            org["category"] = category
            org["category_label"] = CATEGORY_LABELS.get(category, category)
            org.setdefault("accounts", {})
            for platform in PLATFORMS:
                org["accounts"].setdefault(platform, "")
            flat.append(org)
    return flat
