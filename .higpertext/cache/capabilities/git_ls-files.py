"""higpertext Git Ls-Files — inventario compacto de archivos trackeados."""

from __future__ import annotations

import argparse
import json
import subprocess  # nosec B404
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

from higpertext.kernel.infrastructure.logger import get_logger
_log = get_logger()

_SEP = "─" * 50
_PRESET_GLOBS = {
    "all": ["*"],
    "code": [
        "*.py",
        "*.js",
        "*.jsx",
        "*.ts",
        "*.tsx",
        "*.go",
        "*.rs",
        "*.java",
        "*.cs",
    ],
    "python": ["*.py"],
    "web": ["*.js", "*.jsx", "*.ts", "*.tsx", "*.css", "*.scss", "*.html"],
    "docs": ["*.md", "*.txt", "*.rst"],
    "config": ["*.json", "*.jsonc", "*.yaml", "*.yml", "*.toml", "*.ini"],
    "tests": ["tests/*", "test/*", "*_test.*", "test_*"],
}


@dataclass(frozen=True)
class FileEntry:
    """Archivo listado por git con metadatos opcionales."""

    path: str
    size: int = 0
    tracked: bool = True

    @property
    def extension(self) -> str:
        return Path(self.path).suffix or "[sin extensión]"

    @property
    def directory(self) -> str:
        parent = Path(self.path).parent.as_posix()
        return "." if parent == "." else parent


def run_cmd(cmd: list[str]) -> tuple[int, str, str]:
    """Ejecuta comandos git sin shell."""
    res = subprocess.run(cmd, capture_output=True, text=True)  # nosec B603
    return res.returncode, res.stdout.strip(), res.stderr.strip()


def _parse_bool(value: str) -> bool:
    return value.lower() in {"true", "1", "yes", "y"}


def _csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _normalize_globs(value: str | None) -> list[str]:
    globs = _csv(value)
    return [g if any(ch in g for ch in "*/?[]") else f"*.{g.lstrip('.')}" for g in globs]


def _include_globs(include: str | None, extension: str | None, preset: str) -> list[str]:
    explicit = _normalize_globs(include or extension)
    return explicit or _PRESET_GLOBS[preset]


def _matches_any(path: str, globs: list[str]) -> bool:
    return any(fnmatch(path, glob) or fnmatch(Path(path).name, glob) for glob in globs)


def _path_matches(path: str, prefix: str | None) -> bool:
    if not prefix or prefix in {".", "./"}:
        return True
    clean = prefix.strip().strip("/")
    return path == clean or path.startswith(f"{clean}/") or clean in path


def _load_files(include_untracked: bool) -> tuple[list[str], str]:
    ret, out, err = run_cmd(["git", "ls-files"])  # nosec B607
    if ret != 0:
        _log.error(f"[ERROR] {err}")
        sys.exit(1)
    tracked = out.splitlines() if out else []
    if not include_untracked:
        return tracked, "tracked"
    ret_untracked, extra, _ = run_cmd(
        ["git", "ls-files", "--others", "--exclude-standard"]
    )  # nosec B607
    if ret_untracked == 0 and extra:
        tracked.extend(extra.splitlines())
    return sorted(set(tracked)), "tracked+untracked"


def _filter_files(files: list[str], args: argparse.Namespace) -> list[str]:
    include_globs = _include_globs(args.include, args.extension, args.preset)
    exclude_globs = _csv(args.exclude)
    result = []
    for file in files:
        if not _path_matches(file, args.path):
            continue
        if args.pattern and args.pattern not in file:
            continue
        if include_globs != ["*"] and not _matches_any(file, include_globs):
            continue
        if exclude_globs and _matches_any(file, exclude_globs):
            continue
        result.append(file)
    return result


def _entry_for(path: str) -> FileEntry:
    p = Path(path)
    try:
        size = p.stat().st_size if p.exists() else 0
    except OSError:
        size = 0
    return FileEntry(path=path, size=size)


def _sort_entries(entries: list[FileEntry], mode: str) -> list[FileEntry]:
    if mode == "size":
        return sorted(entries, key=lambda e: (-e.size, e.path))
    if mode == "extension":
        return sorted(entries, key=lambda e: (e.extension, e.path))
    return sorted(entries, key=lambda e: e.path)


def _limited(entries: list[FileEntry], max_results: int) -> list[FileEntry]:
    return entries[:max_results]


def _human_size(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    if size >= 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size} B"


def _print_header(args: argparse.Namespace, branch: str, source: str, total: int) -> None:
    _log.info("")
    _log.info("╔" + "═" * 52 + "╗")
    _log.info("║  INVENTARIO DE ARCHIVOS GIT" + " " * 25 + "║")
    _log.info("╚" + "═" * 52 + "╝")
    _log.info(f"  Branch  : {branch or 'desconocido'}")
    _log.info(f"  Fuente  : {source}")
    _log.info(f"  Modo    : {args.mode}")
    if args.path:
        _log.info(f"  Path    : {args.path}")
    if args.pattern:
        _log.info(f"  Filtro  : {args.pattern}")
    _log.info(f"  Total   : {total} archivo(s)")
    _log.info(_SEP)


def _print_list(entries: list[FileEntry], args: argparse.Namespace, total: int) -> None:
    for entry in _limited(entries, args.max_results):
        suffix = ""
        if args.show_size:
            suffix = f"  ({_human_size(entry.size)})"
        marker = "  ⚠ grande" if entry.size / 1024 >= args.large_threshold_kb else ""
        _log.info(f"  {entry.path}{suffix}{marker}")
    _print_truncated_hint(total, args.max_results)


def _print_grouped(entries: list[FileEntry], args: argparse.Namespace, total: int) -> None:
    key_fn = (
        (lambda e: e.extension)
        if args.group_by == "extension"
        else (lambda e: e.directory.split("/")[0])
    )
    groups: dict[str, list[FileEntry]] = defaultdict(list)
    for entry in entries:
        groups[key_fn(entry)].append(entry)
    shown = 0
    for group in sorted(groups):
        if shown >= args.max_results:
            break
        _log.info(f"  {group}/ ({len(groups[group])})")
        for entry in groups[group][: min(5, args.max_results - shown)]:
            _log.info(f"    {entry.path}")
            shown += 1
    _print_truncated_hint(total, args.max_results)


def _print_dirs(entries: list[FileEntry], args: argparse.Namespace) -> None:
    dirs = sorted(
        {_trim_depth(_relative_path(e.directory, args.path), args.max_depth) for e in entries}
    )
    for directory in dirs[: args.max_results]:
        _log.info(f"  {directory}")
    _print_truncated_hint(len(dirs), args.max_results)


def _print_tree(entries: list[FileEntry], args: argparse.Namespace) -> None:
    tree: dict[str, set[str]] = defaultdict(set)
    for entry in entries:
        parts = Path(_relative_path(entry.path, args.path)).parts[: args.max_depth]
        if not parts:
            continue
        parent = "/".join(parts[:-1]) or "."
        tree[parent].add(parts[-1])
    shown = 0
    for parent in sorted(tree):
        if shown >= args.max_results:
            break
        _log.info(f"  {parent}/")
        shown += 1
        for child in sorted(tree[parent])[:5]:
            _log.info(f"    └─ {child}")
    _print_truncated_hint(len(tree), args.max_results)


def _print_summary(entries: list[FileEntry], args: argparse.Namespace) -> None:
    by_ext = Counter(e.extension for e in entries)
    by_dir = Counter(e.directory.split("/")[0] for e in entries)
    large = [e for e in entries if e.size / 1024 >= args.large_threshold_kb]
    _log.info("  Por extensión:")
    for ext, count in by_ext.most_common(10):
        _log.info(f"    {ext}: {count}")
    _log.info("\n  Directorios top:")
    for directory, count in by_dir.most_common(10):
        _log.info(f"    {directory}: {count}")
    if large:
        _log.info("\n  Archivos grandes:")
        for entry in large[:10]:
            _log.info(f"    {entry.path} ({_human_size(entry.size)})")
            if entry.path.endswith((".py", ".js", ".ts", ".tsx")):
                _log.info(
                    f'      sugerencia: mcp__higpertext__common_code-skeletonizer(path="{entry.path}")'
                )
    _log.info("\n  Ejemplos:")
    for entry in entries[: min(10, args.max_results)]:
        _log.info(f"    {entry.path}")


def _print_json(
    entries: list[FileEntry], args: argparse.Namespace, branch: str, source: str
) -> None:
    payload = {
        "branch": branch,
        "source": source,
        "mode": args.mode,
        "total": len(entries),
        "files": [
            {
                "path": e.path,
                "size": e.size,
                "extension": e.extension,
                "directory": e.directory,
            }
            for e in _limited(entries, args.max_results)
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _trim_depth(path: str, max_depth: int) -> str:
    if path == ".":
        return path
    return "/".join(Path(path).parts[:max_depth])


def _relative_path(path: str, base: str) -> str:
    """Muestra árboles relativos al path solicitado para evitar ruido."""
    clean_base = base.strip().strip("/")
    if not clean_base or path in {".", clean_base}:
        return path if not clean_base else "."
    if path.startswith(f"{clean_base}/"):
        return path[len(clean_base) + 1 :]
    return path


def _print_truncated_hint(total: int, max_results: int) -> None:
    if total > max_results:
        _log.info(f"  ... {total - max_results} resultado(s) omitidos; usa filtros o --max_results")


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("debe ser mayor que 0")
    return parsed


def _non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("no puede ser negativo")
    return parsed


def _choice(value: str, allowed: set[str], label: str) -> str:
    if value not in allowed:
        raise argparse.ArgumentTypeError(f"{label} inválido: {value}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Git Ls-Files Task Helper")
    parser.add_argument("--path", default="", help="Prefijo/ruta a explorar")
    parser.add_argument("--pattern", default="", help="Filtro substring opcional")
    parser.add_argument("--include", default="", help="Globs incluidos separados por coma")
    parser.add_argument("--exclude", default="", help="Globs excluidos separados por coma")
    parser.add_argument("--extension", default="", help="Alias de include: py,json o *.py")
    parser.add_argument(
        "--preset",
        default="all",
        type=lambda v: _choice(v, set(_PRESET_GLOBS), "preset"),
    )
    parser.add_argument(
        "--mode",
        default="summary",
        type=lambda v: _choice(v, {"list", "tree", "summary", "dirs", "json"}, "mode"),
    )
    parser.add_argument("--max_results", default="100", type=_positive_int)
    parser.add_argument("--max_depth", default="3", type=_positive_int)
    parser.add_argument("--show_size", default="false")
    parser.add_argument("--large_threshold_kb", default="100", type=_non_negative_int)
    parser.add_argument(
        "--sort",
        default="path",
        type=lambda v: _choice(v, {"path", "size", "extension"}, "sort"),
    )
    parser.add_argument(
        "--group_by",
        default="none",
        type=lambda v: _choice(v, {"none", "dir", "extension"}, "group_by"),
    )
    parser.add_argument("--files_only", default="false")
    parser.add_argument("--json", default="false")
    parser.add_argument("--include_untracked", default="false")
    args = parser.parse_args()

    files, source = _load_files(_parse_bool(args.include_untracked))
    _, branch, _ = run_cmd(["git", "branch", "--show-current"])  # nosec B607
    entries = _sort_entries([_entry_for(path) for path in _filter_files(files, args)], args.sort)

    if args.mode == "json" or _parse_bool(args.json):
        _print_json(entries, args, branch, source)
        return
    if _parse_bool(args.files_only):
        for entry in _limited(entries, args.max_results):
            _log.info(entry.path)
        return

    _print_header(args, branch, source, len(entries))
    if args.mode == "summary":
        _print_summary(entries, args)
    elif args.mode == "tree":
        _print_tree(entries, args)
    elif args.mode == "dirs":
        _print_dirs(entries, args)
    elif args.group_by != "none":
        _print_grouped(entries, args, len(entries))
    else:
        _print_list(entries, args, len(entries))
    _log.info(_SEP)
    _log.info(f"  Total: {len(entries)} archivo(s)")
    _log.info("")
if __name__ == "__main__":
    main()
