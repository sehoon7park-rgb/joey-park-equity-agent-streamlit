"""CLI entrypoint.

    python -m joey_park.cli analyze TICKER [--watchlist]
    python -m joey_park.cli watchlist
"""
from __future__ import annotations

import argparse
import logging
import sys

from joey_park.bootstrap import build_orchestrator
from joey_park.report import render_markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="joey_park", description="Joey Park U.S. Equity Investment Agent")
    sub = parser.add_subparsers(dest="command", required=True)

    analyze_p = sub.add_parser("analyze", help="Run the full pipeline for one ticker")
    analyze_p.add_argument("ticker")
    analyze_p.add_argument("--watchlist", action="store_true", help="Also add the ticker to the watchlist")
    analyze_p.add_argument("-o", "--output", help="Write the markdown report to this file")

    sub.add_parser("watchlist", help="List watchlist tickers")

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    # Windows consoles often default to a legacy codepage (e.g. cp949) that
    # can't encode the em-dashes/arrows used throughout report text.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    orchestrator, db, settings = build_orchestrator()

    if args.command == "analyze":
        if not settings.is_llm_configured():
            print(
                "WARNING: ANTHROPIC_API_KEY is not set — Research/Critic/Decision agents will return "
                "DATA_NOT_AVAILABLE placeholders. Set it in .env to get a real Investment View.",
                file=sys.stderr,
            )
        report = orchestrator.analyze(args.ticker)
        if args.watchlist:
            db.set_watchlist(report.ticker, True)
        markdown = render_markdown(report)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(markdown)
            print(f"Report written to {args.output}")
        else:
            print(markdown)
        return 0

    if args.command == "watchlist":
        rows = db.get_watchlist()
        if not rows:
            print("Watchlist is empty. Run `analyze TICKER --watchlist` to add one.")
        for row in rows:
            print(f"{row['ticker']}\t{row['sector'] or ''}\t{row['industry'] or ''}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
