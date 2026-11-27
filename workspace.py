"""Ingest uploads into fresh job directories. Agent tools only see indexed text."""
import base64
import hashlib
import io
import re
import stat
import zipfile
from pathlib import Path

MIB = 1024 * 1024
TEXT = {".txt", ".md", ".py", ".js", ".ts", ".json", ".toml", ".css", ".html",
        ".yaml", ".yml", ".csv", ".ini", ".rs", ".go", ".java", ".sql"}
RESERVED = re.compile(r"^(con|prn|aux|nul|com[0-9]|lpt[0-9])(\.|$)", re.I)


def safe_name(name):
    if not isinstance(name, str) or len(name) > 180:
        raise ValueError("Invalid filename")
    parts = name.split("/")
    for part in parts:
        if (not re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9_. -]{0,79}", part)
                or part.endswith((".", " ")) or RESERVED.match(part)):
            raise ValueError("Unsafe filename or path")
    return name


def digest(data):
    return hashlib.sha256(data).hexdigest()


def ingest(root, uploads):
    if not isinstance(uploads, list) or len(uploads) > 12:
        raise ValueError("Maximum 12 uploads")
    originals = root / "originals"
    project = root / "project"
    originals.mkdir(parents=True)
    project.mkdir()
    entries, sources, seen = [], [], set()
    total = count = uploaded = 0

    def save(name, content):
        nonlocal total
        total += len(content)
        if len(entries) >= 100 or len(content) > 2*MIB or total > 8*MIB:
            raise ValueError("Expanded project exceeds limits")
        dest = project / safe_name(name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("xb") as f:
            f.write(content)
        entries.append({"path": name, "bytes": len(content), "sha256": digest(content)})

    for item in uploads:
        if not isinstance(item, dict) or set(item) != {"name", "data"}:
            raise ValueError("Invalid upload")
        name = safe_name(item["name"])
        if "/" in name or not isinstance(item["data"], str):
            raise ValueError("Invalid individual upload")
        blob = base64.b64decode(item["data"], validate=True)
        uploaded += len(blob)
        if uploaded > 4*MIB:
            raise ValueError("Uploads exceed 4 MiB")
        with (originals / name).open("xb") as f:
            f.write(blob)
        sources.append({"name": name, "bytes": len(blob), "sha256": digest(blob)})
        if not name.lower().endswith(".zip"):
            if name.casefold() in seen:
                raise ValueError("Duplicate path")
            seen.add(name.casefold())
            save(name, blob)
            continue
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            for member in archive.infolist():
                count += 1
                raw = member.orig_filename
                path = safe_name(raw[:-1] if raw.endswith("/") else raw)
                kind = stat.S_IFMT(member.external_attr >> 16)
                if (count > 120 or kind not in (0, stat.S_IFREG, stat.S_IFDIR)
                        or member.flag_bits & 1 or member.file_size > 2*MIB
                        or member.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                        or path.casefold() in seen):
                    raise ValueError("Unsupported ZIP entry or project limit exceeded")
                seen.add(path.casefold())
                if not member.is_dir():
                    if total + member.file_size > 8*MIB:
                        raise ValueError("Expanded project exceeds 8 MiB")
                    with archive.open(member) as stream:
                        save(path, stream.read(2*MIB+1))
    return {"files": entries, "originals": sources}


def excerpt(root, row):
    name = row["path"]
    path = root / safe_name(name)
    if path.resolve() != root.absolute() / name or not path.is_file():
        raise ValueError("File outside workspace or unavailable")
    if path.suffix.lower() not in TEXT:
        return []
    with path.open("rb") as f:
        data = f.read(32768)
    if b"\x00" in data:
        return []
    try:
        return data.decode("utf-8-sig", errors="strict").splitlines()
    except UnicodeDecodeError:
        return []


def tool(root, manifest, action):
    rows = manifest["files"]
    name = action.get("tool")
    if name in ("inventory", "inspect") and set(action) == {"tool"}:
        if name == "inventory":
            return [{"path": r["path"], "bytes": r["bytes"]} for r in rows]
        types = {}
        for row in rows:
            ext = Path(row["path"]).suffix.lower() or "(no extension)"
            types[ext] = types.get(ext, 0) + 1
        return {"files": len(rows), "extensions": types,
                "manifests": [r["path"] for r in rows if Path(r["path"]).name in
                              ("package.json", "pyproject.toml", "requirements.txt", "Cargo.toml", "go.mod")]}
    if name == "read" and set(action) == {"tool", "path"}:
        row = next((r for r in rows if r["path"] == action["path"]), None)
        if row is None:
            raise ValueError("Unknown project path")
        return [{"path": row["path"], "line": i, "text": line[:240]}
                for i, line in enumerate(excerpt(root, row)[:20], 1)]
    if name == "search" and set(action) == {"tool", "query"}:
        query = action["query"]
        if not isinstance(query, str) or not 1 <= len(query.strip()) <= 80:
            raise ValueError("Invalid literal search")
        hits = []
        for row in rows:
            for i, line in enumerate(excerpt(root, row), 1):
                if query.casefold() in line.casefold():
                    hits.append({"path": row["path"], "line": i, "text": line[:240]})
                    if len(hits) == 20:
                        return hits
        return hits
    raise ValueError("Invalid tool request")
