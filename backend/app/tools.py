import re
from pathlib import Path

from .config import KB_DIR

MAX_READ_BYTES = 200_000


def _safe_path(filename: str) -> Path:
    p = (KB_DIR / filename).resolve()
    if not str(p).startswith(str(KB_DIR)):
        raise ValueError(f"Path escapes KB directory: {filename}")
    return p


def list_files() -> list[dict]:
    if not KB_DIR.exists():
        return []
    out = []
    for p in sorted(KB_DIR.rglob("*.md")):
        rel = p.relative_to(KB_DIR).as_posix()
        out.append({"filename": rel, "size_bytes": p.stat().st_size})
    return out


def read_file(filename: str) -> str:
    p = _safe_path(filename)
    if not p.exists() or not p.is_file():
        return f"ERROR: file not found: {filename}"
    data = p.read_bytes()[:MAX_READ_BYTES]
    return data.decode("utf-8", errors="replace")


def keyword_search(query: str, max_results: int = 20) -> list[dict]:
    if not query.strip() or not KB_DIR.exists():
        return []
    pat = re.compile(re.escape(query), re.IGNORECASE)
    results: list[dict] = []
    for p in sorted(KB_DIR.rglob("*.md")):
        rel = p.relative_to(KB_DIR).as_posix()
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            if pat.search(line):
                results.append({"filename": rel, "line": i, "text": line.strip()[:300]})
                if len(results) >= max_results:
                    return results
    return results


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": (
                "List all markdown files in the Lp(a) knowledge base. "
                "Returns filenames and sizes. Call this first to discover what knowledge is available."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read the full contents of a markdown file from the knowledge base. "
                "Use the filename exactly as returned by list_files."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Relative path of the file, e.g. 'basics.md'.",
                    }
                },
                "required": ["filename"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "keyword_search",
            "description": (
                "Case-insensitive substring search across all markdown files in the knowledge base. "
                "Returns matching lines with filename and line number. Use this to locate relevant files."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Keyword or phrase to search for."},
                    "max_results": {"type": "integer", "default": 20},
                },
                "required": ["query"],
            },
        },
    },
]


def dispatch_tool(name: str, args: dict):
    if name == "list_files":
        return list_files()
    if name == "read_file":
        return read_file(args["filename"])
    if name == "keyword_search":
        return keyword_search(args["query"], int(args.get("max_results", 20)))
    raise ValueError(f"Unknown tool: {name}")
