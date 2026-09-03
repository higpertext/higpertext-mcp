"""Capability common.commit-report — reporte explicativo de commits."""

from __future__ import annotations
import argparse
import hashlib
# Invoca git/htx con lista de argumentos y shell=False.
import subprocess  # nosec B404
from pathlib import Path

from ._report_paths import resolve_root

_ROOT = resolve_root(include_root_in_path=True)

from higpertext.kernel.application.commit_reporter import ReportBuilder, ImpactAnalyzer, CommitParser  # noqa: E402
from higpertext.kernel.config_paths import WORKSPACE_DIR_NAME  # noqa: E402
from higpertext.kernel.infrastructure.output_store import OutputStore  # noqa: E402
from higpertext.kernel.infrastructure.logger import get_logger  # noqa: E402
_log = get_logger()


def _git(args: list[str]) -> str:
    result = subprocess.run(["git"] + args, capture_output=True, text=True, cwd=_ROOT)
    return result.stdout.strip()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Genera reporte explicativo de commits.")
    parser.add_argument("--commit", default="HEAD")
    parser.add_argument("--range", dest="range_", default=None)
    parser.add_argument("--output", default=None)
    parser.add_argument(
        "--no_diff", dest="diff", action="store_false",
        help="Omite las líneas modificadas del reporte."
    )
    parser.set_defaults(diff=True)
    return parser.parse_args()


def _resolve_output(args: argparse.Namespace, short_hash: str) -> Path:
    if args.output:
        return Path(args.output)
    ext = "md"
    out_dir = _ROOT / WORKSPACE_DIR_NAME / "reports" / "commits"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{short_hash}_report.{ext}"


def _write_report(args: argparse.Namespace, report_id: str, content: str) -> Path:
    """Guarda un reporte en la ruta explícita o en el índice unificado."""
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        return out
    return OutputStore(_ROOT).write(
        f"common.commit-report.{report_id}", content, category="commits"
    )


def _build_show_output(ref: str) -> str:
    header = _git(
        [
            "log",
            "-1",
            "--format=%h %s%nAuthor: %an <%ae>%nDate:   %ad",
            "--date=short",
            ref,
        ]
    )
    stat = _git(["show", "--stat", "--format=", ref])
    return header + "\n" + stat


def _get_full_diff(ref: str) -> str:
    return _git(["show", "--format=", "-p", "--unified=3", ref])


def _handle_single(args: argparse.Namespace) -> None:
    ref = args.commit
    show_out = _build_show_output(ref)
    parser = CommitParser()
    report = parser.parse_show(show_out)
    if report is None:
        _log.error(f"[ERROR] No se pudo parsear el commit: {ref}")
        sys.exit(1)
    analysis = ImpactAnalyzer().analyze(report)
    builder = ReportBuilder()
    full_diff = _get_full_diff(ref) if args.diff else None
    content = builder.to_markdown(report, analysis, diff=full_diff)
    out = _write_report(args, report.commit.short_hash, content)
    _print_summary(report, analysis, out)


def _handle_range(args: argparse.Namespace) -> None:
    log_out = _git(["log", "--format=%h|||%s|||%an <%ae>|||%ad", "--date=short", args.range_])
    commits = CommitParser().parse_log(log_out)
    if not commits:
        _log.error(f"[ERROR] No se encontraron commits en el rango: {args.range_}")
        sys.exit(1)
    lines = [
        f"# Commit Range Report — `{args.range_}`\n",
        f"**{len(commits)} commits**\n\n---\n",
    ]
    for commit in commits:
        show_out = _build_show_output(commit.hash)
        report = CommitParser().parse_show(show_out)
        if report is None:
            continue
        analysis = ImpactAnalyzer().analyze(report)
        lines.append(ReportBuilder().to_markdown(report, analysis, diff=_get_full_diff(commit.hash)))
        lines.append("\n---\n")
    content = "\n".join(lines)
    range_id = hashlib.sha256(args.range_.encode("utf-8")).hexdigest()[:12]
    out = _write_report(args, f"range-{range_id}", content)
    _log.ok(f"[SUCCESS] Reporte de {len(commits)} commits escrito en: {out}")


def _print_summary(report, analysis, out: Path) -> None:
    c = report.commit
    _log.info("╔─ HIGPERTEXT · Commit Report ────────────────────────────────")
    _log.info(f"│  Commit   : {c.short_hash} ({c.commit_type.value})")
    _log.info(f"│  Scope    : {c.scope or '—'}")
    _log.info(f"│  Autor    : {c.author}")
    _log.info(f"│  Fecha    : {c.date}")
    _log.info(f"│  Archivos : {report.changed_files_count}")
    _log.info(f"│  +Lines   : {report.total_additions}  -Lines: {report.total_deletions}")
    _log.info(f"│  Tags     : {', '.join(analysis.impact_tags)}")
    _log.info(f"│  Reporte  : {out.relative_to(_ROOT)}")
    _log.info("╚───────────────────────────────────────────────────────")
    _log.info(f"\n{analysis.summary}")
    _log.ok(f"\n[SUCCESS] Reporte generado: {out}")


def main() -> None:
    args = _parse_args()
    if args.range_:
        _handle_range(args)
    else:
        _handle_single(args)


if __name__ == "__main__":
    main()
