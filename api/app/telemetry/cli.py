"""`python -m app.telemetry.cli export|purge`."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from app.config import get_settings
from app.telemetry.logger import export_csv, purge


def main() -> None:
    """Export logs to CSV or purge all logged data."""
    ap = argparse.ArgumentParser(description="Research log utilities")
    sub = ap.add_subparsers(dest="cmd", required=True)
    exp = sub.add_parser("export", help="export turns to CSV")
    exp.add_argument("--out", default=None)
    pg = sub.add_parser("purge", help="delete ALL logged research data")
    pg.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    args = ap.parse_args()
    s = get_settings()

    if args.cmd == "export":
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        out = (
            s.resolve(Path(args.out)) if args.out else s.data_dir / "exports" / f"turns-{stamp}.csv"
        )
        n = export_csv(s.log_dir, out)
        print(f"Exported {n} turns to {out}")
        return

    if not args.yes:
        answer = input(
            f"Delete all research logs under {s.log_dir} and exports/audio? Type 'purge': "
        )
        if answer.strip() != "purge":
            print("Aborted.")
            return
    removed = purge(s.data_dir, s.log_dir)
    print("Removed:\n  " + "\n  ".join(removed) if removed else "Nothing to remove.")


if __name__ == "__main__":
    main()
