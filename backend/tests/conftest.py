from pathlib import Path

import pytest


@pytest.fixture
def kb(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KB_DIR at a temp dir populated with fixture markdown files."""
    (tmp_path / "basics.md").write_text(
        "# Lp(a) basics\n\nLipoprotein(a) is a risk factor.\nApo(a) is covalently bound.\n",
        encoding="utf-8",
    )
    (tmp_path / "trials.md").write_text(
        "# Trials\n\nHORIZON studies pelacarsen.\nOCEAN(a) studies olpasiran.\n",
        encoding="utf-8",
    )
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "nested.md").write_text("# Nested\n\nnested APO(a) content\n", encoding="utf-8")

    # Also create a non-md file that should be ignored.
    (tmp_path / "ignore.txt").write_text("not markdown", encoding="utf-8")

    from app import tools

    monkeypatch.setattr(tools, "KB_DIR", tmp_path.resolve())
    return tmp_path
