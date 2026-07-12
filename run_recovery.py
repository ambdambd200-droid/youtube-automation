"""
VARY — Pipeline Recovery Script.
Detects failed pipeline runs and re-queues them automatically.

This is the bridge between the Pipeline Watchdog and GitHub Actions.
It can be run:
  - Manually:  python run_recovery.py
  - In CI:     python run_recovery.py --retry
  - As dry-run: python run_recovery.py --check

The recovery logic:
  1. Load the pipeline state from pipeline_state.json
  2. Find runs with status="failed" within the last FAILURE_WINDOW_HOURS
  3. Check if retry_count < MAX_RETRIES_PER_RUN
  4. For each eligible failure, print the re-run command or execute it

Usage:
    python run_recovery.py              # Full check + retry eligible failures
    python run_recovery.py --check      # Dry-run: show what would be retried
    python run_recovery.py --force      # Retry even if max retries exceeded
    python run_recovery.py --recent     # Show recent pipeline activity
    python run_recovery.py --stuck      # Find and handle stuck runs
    python run_recovery.py --daily      # Check/recover daily pipeline only
    python run_recovery.py --weekly     # Check/recover weekly pipeline only
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from modules.pipeline_watchdog import (
    get_failed_runs_for_retry,
    get_failed_runs,
    get_stuck_runs,
    get_runs_summary,
    get_recovery_command,
    mark_retried,
    notify_exhausted_retries,
    MAX_RETRIES_PER_RUN,
    FAILURE_WINDOW_HOURS,
    detect_missed_runs,
)


RETRY_DELAY = 60  # seconds between retries


# ── Recovery Logic ───────────────────────────────────────────


def check_and_retry(dry_run=False, force=False, pipeline_type=None):
    """Check for failed runs and retry them.

    Args:
        dry_run: If True, only print what would be retried (no execution).
        force: If True, retry even if max retries exceeded.
        pipeline_type: If "daily" or "weekly", only check that type.

    Returns:
        Dict with recovery results.
    """
    print(f"\n{'='*60}")
    print(f"  VARY — Pipeline Recovery Check")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    # ── 1. Check for failed runs eligible for retry ───────
    eligible = get_failed_runs_for_retry()
    if pipeline_type:
        eligible = [r for r in eligible if r.get("pipeline_type") == pipeline_type]

    if not eligible:
        print(f"\n  ✅ No failed runs eligible for retry.")
    else:
        print(f"\n  🔴 {len(eligible)} failed run(s) eligible for retry:")
        for r in eligible:
            print(f"    [{r['pipeline_type']}] {r['pipeline_id']} — "
                  f"stage={r['stage']}, retry #{r['retry_count']}/{MAX_RETRIES_PER_RUN}")
            cmd = get_recovery_command(r)
            if not cmd:
                print(f"      ⚠ No recovery command for type={r['pipeline_type']}")
                continue

            if dry_run:
                print(f"      [DRY-RUN] Would run: {cmd}")
            else:
                mark_retried(r["pipeline_id"])
                print(f"      Running: {cmd}...")
                time.sleep(RETRY_DELAY)  # delay between retries
                result = subprocess.run(cmd, shell=True, capture_output=False)
                if result.returncode == 0:
                    print(f"      ✅ Recovery successful: {r['pipeline_id']}")
                else:
                    print(f"      ❌ Recovery also failed for {r['pipeline_id']} "
                          f"(exit: {result.returncode})")

    # ── 2. Check for stuck runs (timed out) ───────────────
    stuck = get_stuck_runs()
    if pipeline_type:
        stuck = [r for r in stuck if r.get("pipeline_type") == pipeline_type]

    if stuck:
        print(f"\n  ⏸ {len(stuck)} stuck run(s) detected "
              f"(running >180 min without update):")
        for r in stuck:
            print(f"    [{r['pipeline_type']}] {r['pipeline_id']} — started {r.get('start_time')}")
        # Stuck runs are automatically recovered on next retry cycle since
        # get_failed_runs_for_retry() filters out 'running' runs, and the
        # stuck run's pipeline_id won't conflict with new retries.

    # ── 3. Check for missed runs ──────────────────────────
    missed = detect_missed_runs()
    if pipeline_type:
        missed = [m for m in missed if m["type"] == pipeline_type]

    if missed:
        print(f"\n  ⚠ {len(missed)} missed run(s) detected in last 24h:")
        for m in missed:
            print(f"    [{m['type']}] {m['gap']} of {m['expected']} uploads missing")

    # ── 4. Send webhook alerts for exhausted retries ─────
    exhausted_count = notify_exhausted_retries()
    if exhausted_count > 0:
        print(f"\n  🚨 {exhausted_count} run(s) exhausted all retries. Alert sent.")

    # ── 5. Summary ────────────────────────────────────────
    summary = get_runs_summary()
    print(f"\n  {'─'*50}")
    print(f"  Pipeline state summary:")
    print(f"    Total runs tracked:  {summary['total_runs']}")
    print(f"    Completed:           {summary['completed']}")
    print(f"    Failed:              {summary['failed']}")
    print(f"    Recent failures (4h): {summary['recent_failures_4h']}")
    print(f"  {'='*60}\n")

    return {
        "checked_at": datetime.now().isoformat(),
        "eligible_for_retry": len(eligible),
        "stuck_runs": len(stuck),
        "missed_runs": len(missed),
        "total_tracked": summary["total_runs"],
        "completed": summary["completed"],
        "failed": summary["failed"],
    }


def show_recent_activity():
    """Show the most recent pipeline activity across all logs."""
    summary = get_runs_summary()

    print(f"\n{'='*60}")
    print(f"  VARY — Recent Pipeline Activity")
    print(f"{'='*60}")

    print(f"\n  Summary from watchdog state:")
    print(f"    Total runs tracked:  {summary['total_runs']}")
    print(f"    Completed:           {summary['completed']}")
    print(f"    Failed:              {summary['failed']}")
    print(f"    Running:             {summary['running']}")
    print(f"    Recovery retries:    {summary['recovery_retries']}")

    # Recent runs
    recent = summary.get("recent_activity", [])
    if recent:
        print(f"\n  Last {len(recent)} runs:")
        for r in recent:
            status_icon = {"completed": "✅", "failed": "❌", "running": "⏳"}.get(
                r["status"], "❓"
            )
            err = f" — {r['error'][:60]}" if r.get("error") else ""
            print(f"    {status_icon} [{r['type']}] {r['id']} "
                  f"stage={r['stage']}{err}")

    # Recent failures
    failures = get_failed_runs()
    if failures:
        print(f"\n  All recent failures ({len(failures)}):")
        for f in failures:
            print(f"    ❌ [{f['pipeline_type']}] {f['pipeline_id']}"
                  f" — stage={f['stage']}, error={f.get('error', 'N/A')[:80]}")

    # Stuck runs
    stuck = get_stuck_runs()
    if stuck:
        print(f"\n  ⏸ Stuck runs ({len(stuck)}):")
        for s in stuck:
            print(f"    {s['pipeline_id']} — started {s.get('start_time')}")

    print()


# ── CLI Entry Point ──────────────────────────────────────────


def main():
    import argparse
    parser = argparse.ArgumentParser(description="VARY — Pipeline Recovery")
    parser.add_argument("--check", action="store_true",
                        help="Dry-run: show what would be retried (no execution)")
    parser.add_argument("--force", action="store_true",
                        help="Force retry even if max retries exceeded")
    parser.add_argument("--recent", action="store_true",
                        help="Show recent pipeline activity")
    parser.add_argument("--stuck", action="store_true",
                        help="Find and report stuck runs")
    parser.add_argument("--daily", action="store_true",
                        help="Check/recover daily pipeline only")
    parser.add_argument("--weekly", action="store_true",
                        help="Check/recover weekly pipeline only")
    args = parser.parse_args()

    # Determine pipeline type filter
    pipeline_type = None
    if args.daily:
        pipeline_type = "daily"
    elif args.weekly:
        pipeline_type = "weekly"

    if args.recent:
        show_recent_activity()
        return

    if args.stuck:
        stuck = get_stuck_runs()
        if stuck:
            print(f"Stuck runs ({len(stuck)}):")
            for s in stuck:
                print(f"  {s['pipeline_id']} — started {s.get('start_time')}")
        else:
            print("No stuck runs detected.")
        return

    # Default: full check + retry
    check_and_retry(dry_run=args.check, force=args.force,
                    pipeline_type=pipeline_type)


if __name__ == "__main__":
    main()
