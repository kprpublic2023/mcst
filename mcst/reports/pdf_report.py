"""HTML -> PDF 변환 (WeasyPrint)."""
from __future__ import annotations

from pathlib import Path


def render_pdf(html: str, out_path: Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from weasyprint import HTML  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "WeasyPrint를 불러올 수 없습니다. `pip install weasyprint` 와 시스템 의존성"
            "(libpango, libcairo 등) 설치를 확인해 주세요."
        ) from e
    HTML(string=html).write_pdf(str(out_path))
    return out_path
