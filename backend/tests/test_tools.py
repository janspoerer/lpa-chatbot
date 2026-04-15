from pathlib import Path

import pytest

from app import tools


def test_list_files_returns_all_markdown_sorted(kb: Path):
    files = tools.list_files()
    names = [f["filename"] for f in files]
    assert names == ["basics.md", "sub/nested.md", "trials.md"]
    assert all(f["size_bytes"] > 0 for f in files)


def test_list_files_ignores_non_markdown(kb: Path):
    files = tools.list_files()
    assert not any(f["filename"].endswith(".txt") for f in files)


def test_list_files_returns_empty_when_kb_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    missing = tmp_path / "nope"
    monkeypatch.setattr(tools, "KB_DIR", missing)
    assert tools.list_files() == []


def test_read_file_returns_contents(kb: Path):
    content = tools.read_file("basics.md")
    assert "Lipoprotein(a)" in content
    assert "Apo(a)" in content


def test_read_file_supports_nested_paths(kb: Path):
    content = tools.read_file("sub/nested.md")
    assert "nested APO(a) content" in content


def test_read_file_missing_file_returns_error_string(kb: Path):
    result = tools.read_file("does-not-exist.md")
    assert result.startswith("ERROR: file not found")


def test_read_file_rejects_path_traversal(kb: Path, tmp_path: Path):
    # A file outside the KB the agent must not be able to read.
    secret = tmp_path.parent / "secret.md"
    secret.write_text("SECRET", encoding="utf-8")
    with pytest.raises(ValueError, match="escapes KB directory"):
        tools.read_file("../secret.md")


def test_read_file_rejects_absolute_path_escape(kb: Path):
    with pytest.raises(ValueError, match="escapes KB directory"):
        tools.read_file("/etc/passwd")


def test_keyword_search_finds_matches_with_line_numbers(kb: Path):
    results = tools.keyword_search("pelacarsen")
    assert len(results) == 1
    r = results[0]
    assert r["filename"] == "trials.md"
    assert r["line"] == 3
    assert "pelacarsen" in r["text"].lower()


def test_keyword_search_is_case_insensitive(kb: Path):
    lower = tools.keyword_search("apo(a)")
    upper = tools.keyword_search("APO(A)")
    assert len(lower) == len(upper) >= 2  # basics.md + sub/nested.md


def test_keyword_search_empty_query_returns_empty(kb: Path):
    assert tools.keyword_search("") == []
    assert tools.keyword_search("   ") == []


def test_keyword_search_no_matches(kb: Path):
    assert tools.keyword_search("zzz-no-such-token") == []


def test_keyword_search_respects_max_results(kb: Path):
    # "Lp(a)" appears in multiple files; cap at 1.
    results = tools.keyword_search("Lp(a)", max_results=1)
    assert len(results) == 1


def test_dispatch_tool_routes_to_list_files(kb: Path):
    assert isinstance(tools.dispatch_tool("list_files", {}), list)


def test_dispatch_tool_routes_to_read_file(kb: Path):
    result = tools.dispatch_tool("read_file", {"filename": "basics.md"})
    assert "Lipoprotein(a)" in result


def test_dispatch_tool_routes_to_keyword_search(kb: Path):
    result = tools.dispatch_tool("keyword_search", {"query": "pelacarsen"})
    assert len(result) == 1


def test_dispatch_tool_unknown_name_raises(kb: Path):
    with pytest.raises(ValueError, match="Unknown tool"):
        tools.dispatch_tool("nope", {})


def test_tool_schemas_shape():
    names = {t["function"]["name"] for t in tools.TOOL_SCHEMAS}
    assert names == {"list_files", "read_file", "keyword_search"}
    for t in tools.TOOL_SCHEMAS:
        assert t["type"] == "function"
        assert "description" in t["function"]
        assert "parameters" in t["function"]
