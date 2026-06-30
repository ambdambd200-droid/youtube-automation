"""
VARY Pipeline Watchdog — crash detection and auto-retry safety net.

Tracks every pipeline run (daily + weekly) with persistent state so we can
detect failures even after the process exits. Provides tools to re-queue
failed runs and alert when retries are exhausted.

Data model:
  - Each pipeline run is stored in pipeline_state.json with:
    - pipeline_id: unique run identifier
    - pipeline_type: "daily" or "weekly"
    - status: "running" | "completed" | "failed"
    - stage: the last known stage (e.g. "download", "editing", "upload")
    - error: truncated error message if failed
    - start_time, end_time: ISO timestamps
    - retry_count: how many times this specific pipeline run has been retried
    - exit_code: the process exit code (or null)
"""
import json
import os
import sys
import traceback
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import LOG_DIR, ALERT_WEBHOOK_URL


PIPELINE_STATE_FILE = os.path.join(LOG_DIR, "pipeline_state.json")
MAX_RETRIES_PER_RUN = 2       # Max retries per scheduled window
FAILURE_WINDOW_HOURS = 4      # Consider failures within this window as "recent"
PRUNE_DAYS = 7               # Delete pipeline state entries older than this
STATE_MAX_ENTRIES = 100       # Max entries kept after pruning (per type)
DAILY_PIPELINE_LOG = os.path.join(LOG_DIR, "pipeline_log.jsonl")
WEEKLY_PIPELINE_LOG = os.path.join(LOG_DIR, "weekly_pipeline_log.jsonl")


# ── State Management ─────────────────────────────────────────


def _load_state():
    """Load the full pipeline state from disk."""
    if os.path.exists(PIPELINE_STATE_FILE):
        try:
            with open(PIPELINE_STATE_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"runs": [], "recovery_retries": 0}


def _save_state(state):
    """Save pipeline state to disk, pruning old entries first."""
    prune_old_state(state)
    os.makedirs(os.path.dirname(PIPELINE_STATE_FILE), exist_ok=True)
    with open(PIPELINE_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, default=str)


def generate_pipeline_id(pipeline_type):
    """Generate a unique pipeline run identifier."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{pipeline_type}_{ts}"


# ── Run Registration ────────────────────────────────────────


def register_run_start(pipeline_type):
    """Register a pipeline run as started. Returns the pipeline_id.

    Called at the very beginning of a pipeline, before any work begins.
    """
    state = _load_state()
    pipeline_id = generate_pipeline_id(pipeline_type)

    state["runs"].append({
        "pipeline_id": pipeline_id,
        "pipeline_type": pipeline_type,
        "status": "running",
        "stage": "starting",
        "error": None,
        "start_time": datetime.now().isoformat(),
        "end_time": None,
        "retry_count": 0,
        "exit_code": None,
    })

    # Trim old runs (keep last 100)
    state["runs"] = state["runs"][-100:]
    _save_state(state)

    print(f"  [watchdog] Run registered: {pipeline_id}", flush=True)
    return pipeline_id


def register_stage(pipeline_id, stage):
    """Update the current stage of a running pipeline.

    Called after each pipeline step completes successfully.
    """
    state = _load_state()
    for run in state["runs"]:
        if run["pipeline_id"] == pipeline_id:
            run["stage"] = stage
            _save_state(state)
            return
    print(f"  [watchdog] WARNING: No run found for {pipeline_id}", flush=True)


def register_run_complete(pipeline_id, exit_code=0):
    """Mark a pipeline run as completed successfully.

    Called at the very end of a successful pipeline.
    """
    state = _load_state()
    for run in state["runs"]:
        if run["pipeline_id"] == pipeline_id:
            run["status"] = "completed"
            run["stage"] = "complete"
            run["end_time"] = datetime.now().isoformat()
            run["exit_code"] = exit_code
            _save_state(state)
            print(f"  [watchdog] Run completed: {pipeline_id}", flush=True)
            return
    print(f"  [watchdog] WARNING: No run found for {pipeline_id}", flush=True)


def register_run_failure(pipeline_id, error_message, stage=None):
    """Mark a pipeline run as failed with an error.

    Called from exception handlers. Records the error and increments retry count.
    """
    state = _load_state()
    for run in state["runs"]:
        if run["pipeline_id"] == pipeline_id:
            run["status"] = "failed"
            run["end_time"] = datetime.now().isoformat()
            run["error"] = str(error_message)[:500]  # truncate long errors
            run["exit_code"] = 1
            if stage:
                run["stage"] = stage
            _save_state(state)
            print(f"  [watchdog] Run FAILED: {pipeline_id} — {error_message[:100]}", flush=True)
            return
    print(f"  [watchdog] WARNING: No run found for {pipeline_id}", flush=True)


# ── Crash Detection ──────────────────────────────────────────


def get_failed_runs(window_hours=FAILURE_WINDOW_HOURS):
    """Get pipeline runs that failed within the last N hours.

    Returns a list of failed run dicts sorted by start_time (newest first).
    Useful for recovery checks and alerting.
    """
    state = _load_state()
    cutoff = datetime.now() - timedelta(hours=window_hours)
    failures = []

    for run in state["runs"]:
        if run["status"] != "failed":
            continue
        try:
            start = datetime.fromisoformat(run.get("start_time", ""))
            if start < cutoff:
                continue
        except (ValueError, TypeError):
            continue
        failures.append(run)

    return sorted(failures, key=lambda r: r.get("start_time", ""), reverse=True)


def get_stuck_runs(timeout_minutes=180):
    """Get runs that are stuck in 'running' status beyond the timeout.

    These are pipelines that crashed without updating their status
    (e.g., killed by OOM, network drop, or hard crash).
    """
    state = _load_state()
    cutoff = datetime.now() - timedelta(minutes=timeout_minutes)
    stuck = []

    for run in state["runs"]:
        if run["status"] != "running":
            continue
        try:
            start = datetime.fromisoformat(run.get("start_time", ""))
            if start < cutoff:
                stuck.append(run)
        except (ValueError, TypeError):
            continue

    return stuck


def get_runs_summary():
    """Get a quick summary of pipeline health for the dashboard."""
    state = _load_state()
    total = len(state["runs"])
    completed = sum(1 for r in state["runs"] if r["status"] == "completed")
    failed = sum(1 for r in state["runs"] if r["status"] == "failed")
    running = sum(1 for r in state["runs"] if r["status"] == "running")
    recent_failures = len(get_failed_runs())

    # Last 10 runs
    recent = sorted(state["runs"],
                    key=lambda r: r.get("start_time", ""), reverse=True)[:10]

    return {
        "total_runs": total,
        "completed": completed,
        "failed": failed,
        "running": running,
        "recent_failures_4h": recent_failures,
        "recovery_retries": state.get("recovery_retries", 0),
        "recent_activity": [
            {
                "id": r["pipeline_id"],
                "type": r["pipeline_type"],
                "status": r["status"],
                "stage": r["stage"],
                "error": r.get("error"),
                "start": r.get("start_time"),
            }
            for r in recent
        ],
    }


# ── Public State Access ─────────────────────────────────────


def load_state():
    """Public wrapper to load the full pipeline state from disk."""
    return _load_state()


def save_state(state):
    """Public wrapper to save pipeline state to disk."""
    _save_state(state)


# ── Pruning ──────────────────────────────────────────────────


def prune_old_state(state=None, days=None):
    """Remove pipeline state entries older than `days` days.

    Keeps the state file clean by removing old entries. Also limits
    the total number of entries to STATE_MAX_ENTRIES (keeps the most
    recent ones). Called automatically by _save_state() before writing.

    Args:
        state: State dict. If None, loads current state.
        days: Entries older than this many days are pruned. Default PRUNE_DAYS.

    Returns:
        (pruned_count, remaining_count) tuple.
    """
    if state is None:
        state = _load_state()

    days = days or PRUNE_DAYS
    cutoff = datetime.now() - timedelta(days=days)
    runs = state.get("runs", [])
    before = len(runs)

    # Keep entries newer than cutoff OR entries still running (in-progress)
    state["runs"] = []
    for r in runs:
        if r.get("status") == "running":
            state["runs"].append(r)
            continue
        start = _parse_start_time(r)
        if start is not None and start > cutoff:
            state["runs"].append(r)

    # Also cap total entries to STATE_MAX_ENTRIES, keeping the most recent
    if len(state["runs"]) > STATE_MAX_ENTRIES:
        sort_key = lambda r: _parse_start_time(r) or datetime.min
        state["runs"].sort(key=sort_key, reverse=True)
        state["runs"] = state["runs"][:STATE_MAX_ENTRIES]

    pruned = before - len(state["runs"])
    return pruned, len(state["runs"])


def _parse_start_time(run):
    """Safely parse a run's start_time."""
    try:
        return datetime.fromisoformat(run.get("start_time", ""))
    except (ValueError, TypeError):
        return None


# ── Recovery Logic ───────────────────────────────────────────


def _load_pipeline_logs(log_path, max_entries=50):
    """Load entries from a pipeline JSONL log."""
    if not os.path.exists(log_path):
        return []
    entries = []
    try:
        with open(log_path, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except IOError:
        pass
    return entries[-max_entries:]


def detect_missed_runs():
    """Detect runs that should have happened but didn't complete.

    Compares the pipeline logs against the scheduled posting times.
    For each scheduled slot in the last 24h, checks if a successful
    upload happened.

    Returns:
        List of missed run descriptors.
    """
    from config import get_posting_times

    missed = []

    # Check daily pipeline log for uploads
    daily_logs = _load_pipeline_logs(DAILY_PIPELINE_LOG)
    weekly_logs = _load_pipeline_logs(WEEKLY_PIPELINE_LOG)

    # Count successful uploads in last 24h
    cutoff_24h = (datetime.now() - timedelta(hours=24)).isoformat()
    daily_uploads = sum(1 for e in daily_logs
                        if e.get("stage") == "upload"
                        and e.get("status") == "success"
                        and e.get("timestamp", "") > cutoff_24h)
    weekly_uploads = sum(1 for e in weekly_logs
                         if e.get("stage") == "upload"
                         and e.get("status") == "success"
                         and e.get("timestamp", "") > cutoff_24h)

    # Expect 3 daily uploads per day (morning, afternoon, night)
    if daily_uploads < 3:
        daily_starts = sum(1 for e in daily_logs
                           if e.get("stage") == "content_selection"
                           and e.get("timestamp", "") > cutoff_24h)
        missed.append({
            "type": "daily",
            "expected": 3,
            "actual_uploads": daily_uploads,
            "actual_starts": daily_starts,
            "gap": max(0, 3 - daily_uploads),
        })

    # Weekly: 1 upload expected per week on Sunday
    cutoff_7d = (datetime.now() - timedelta(days=7)).isoformat()
    weekly_7d_uploads = sum(1 for e in weekly_logs
                            if e.get("stage") == "upload"
                            and e.get("status") == "success"
                            and e.get("timestamp", "") > cutoff_7d)
    weekly_7d_starts = sum(1 for e in weekly_logs
                           if e.get("stage") == "content_selection"
                           and e.get("timestamp", "") > cutoff_7d)

    if weekly_7d_uploads < 1 and weekly_7d_starts >= 0:
        missed.append({
            "type": "weekly",
            "expected": 1,
            "actual_uploads": weekly_7d_uploads,
            "actual_starts": weekly_7d_starts,
            "gap": max(0, 1 - weekly_7d_uploads),
        })

    return missed


def get_failed_runs_for_retry():
    """Get failed runs eligible for automated retry.

    Criteria:
    - Failed within the last FAILURE_WINDOW_HOURS
    - Retry count < MAX_RETRIES_PER_RUN
    - Not currently being retried (no 'running' entry for same pipeline_id)

    Returns:
        List of run dicts that should be retried.
    """
    state = _load_state()
    cutoff = datetime.now() - timedelta(hours=FAILURE_WINDOW_HOURS)
    running_ids = {r["pipeline_id"] for r in state["runs"] if r["status"] == "running"}

    eligible = []
    for run in state["runs"]:
        if run["status"] != "failed":
            continue
        if run["retry_count"] >= MAX_RETRIES_PER_RUN:
            continue
        if run["pipeline_id"] in running_ids:
            continue  # already being retried
        try:
            start = datetime.fromisoformat(run.get("start_time", ""))
            if start < cutoff:
                continue
        except (ValueError, TypeError):
            continue
        eligible.append(run)

    return eligible


def mark_retried(pipeline_id):
    """Increment the retry count for a failed pipeline run."""
    state = _load_state()
    for run in state["runs"]:
        if run["pipeline_id"] == pipeline_id:
            run["retry_count"] += 1
            _save_state(state)
            return run["retry_count"]
    return 0


def get_recovery_command(failed_run):
    """Get the shell command to re-run a failed pipeline.

    Args:
        failed_run: A run dict from get_failed_runs_for_retry().

    Returns:
        A shell command string, or None if the type is unknown.
    """
    ptype = failed_run.get("pipeline_type")
    if ptype == "daily":
        return "python run_pipeline.py"
    elif ptype == "weekly":
        return "python run_weekly_pipeline.py"
    return None


# ── Webhook Alerts ───────────────────────────────────────────

# Deliberately lightweight: no retry logic, no batching, no resilience.
# If the webhook fails, we print a warning and move on.
# The alert will fire again on the next recovery check cycle.


def send_alert(message):
    """Send a message to the configured webhook (Discord or Slack).

    Auto-detects the webhook type from the URL:
    - discord.com/api/webhooks/ → Discord (\"content\" payload)
    - hooks.slack.com/services/ → Slack (\"text\" payload)

    If ALERT_WEBHOOK_URL is not set or empty, silently skips.
    If the webhook call fails, prints a warning but does not raise.

    Args:
        message: Plain-text message to send.
    """
    url = ALERT_WEBHOOK_URL.strip()
    if not url:
        return  # No webhook configured, silently skip

    try:
        import requests

        # Detect webhook type from URL
        if "discord.com/api/webhooks/" in url:
            payload = {"content": message[:2000]}  # Discord: 2000 char limit
        elif "hooks.slack.com/services/" in url:
            payload = {"text": message}
        else:
            # Generic: assume Slack-compatible JSON payload
            payload = {"text": message}

        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        print(f"  [watchdog] Alert sent to webhook", flush=True)

    except ImportError:
        print(f"  [watchdog] WARNING: requests not installed — cannot send alert", flush=True)
    except Exception as e:
        print(f"  [watchdog] WARNING: Failed to send alert: {e}", flush=True)


def get_exhausted_runs(window_hours=FAILURE_WINDOW_HOURS):
    """Get failed runs that have exhausted their retries.

    These are runs where:
    - Status = "failed"
    - retry_count >= MAX_RETRIES_PER_RUN
    - Start time is within the last `window_hours` hours

    Returns:
        List of run dicts that should trigger an alert.
    """
    state = _load_state()
    cutoff = datetime.now() - timedelta(hours=window_hours)
    exhausted = []

    for run in state["runs"]:
        if run["status"] != "failed":
            continue
        if run.get("retry_count", 0) < MAX_RETRIES_PER_RUN:
            continue
        try:
            start = datetime.fromisoformat(run.get("start_time", ""))
            if start < cutoff:
                continue
        except (ValueError, TypeError):
            continue

        # Build a human-readable alert
        summary = {
            "pipeline_id": run["pipeline_id"],
            "pipeline_type": run.get("pipeline_type", "unknown"),
            "stage": run.get("stage", "unknown"),
            "error": run.get("error", "unknown")[:200],
            "retry_count": run.get("retry_count", 0),
            "start_time": run.get("start_time", ""),
        }
        exhausted.append(summary)

    return exhausted


def notify_exhausted_retries(window_hours=FAILURE_WINDOW_HOURS):
    """Find runs with exhausted retries and send a webhook alert.

    Designed to be called from the recovery workflow after attempting
    recovery. Groups all exhausted runs into a single alert message.

    Args:
        window_hours: Look back window for recent failures.

    Returns:
        Number of exhausted runs found (0 means nothing to alert on).
    """
    exhausted = get_exhausted_runs(window_hours=window_hours)
    if not exhausted:
        return 0

    # Build a single alert message summarizing all exhausted runs
    lines = ["🚨 **VARY Pipeline — Retries Exhausted**"]
    lines.append("")

    for r in exhausted:
        ptype = r["pipeline_type"].upper()
        run_id = r["pipeline_id"]
        stage = r["stage"]
        error = r["error"][:100]
        retries = r["retry_count"]
        lines.append(f"**{ptype}** `{run_id}`")
        lines.append(f"   Stage: {stage} | Retries: {retries}")
        lines.append(f"   Error: {error}")
        lines.append("")

    # Add context about what to do
    lines.append("Next steps:")
    lines.append("1. Check the GitHub Actions logs for this run.")
    lines.append("2. Run recovery: `python run_recovery.py --force`")
    lines.append("3. Check disk space and YouTube quota.")

    message = "\n".join(lines)
    send_alert(message)

    print(f"  [watchdog] Alert sent for {len(exhausted)} exhausted run(s)", flush=True)
    return len(exhausted)


# ── CLI Entry Point ──────────────────────────────────────────


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="VARY Pipeline Watchdog")
    parser.add_argument("--status", action="store_true", help="Show pipeline health summary")
    parser.add_argument("--failures", action="store_true", help="Show recent failures")
    parser.add_argument("--stuck", action="store_true", help="Show stuck runs")
    parser.add_argument("--missed", action="store_true", help="Detect missed runs")
    parser.add_argument("--retry-list", action="store_true", help="List runs eligible for retry")
    parser.add_argument("--prune", type=int, nargs="?", const=PRUNE_DAYS, default=None,
                        help=f"Prune old entries (default: {PRUNE_DAYS} days)")
    parser.add_argument("--notify", action="store_true",
                        help="Send webhook alerts for exhausted retries")
    args = parser.parse_args()

    if args.prune is not None:
        state = _load_state()
        pruned, remaining = prune_old_state(state, days=args.prune)
        _save_state(state)
        print(f"Pruned {pruned} old entries. {remaining} entries remaining.")
        return

    if args.notify:
        count = notify_exhausted_retries()
        if count == 0:
            print("No exhausted retries found. No alert sent.")
        else:
            print(f"Alert sent for {count} exhausted run(s).")
        return

    if args.status:
        summary = get_runs_summary()
        print(json.dumps(summary, indent=2, default=str))

    if args.failures:
        failures = get_failed_runs()
        if failures:
            print(f"Recent failures ({len(failures)}):")
            for f in failures:
                print(f"  [{f['pipeline_type']}] {f['pipeline_id']} — "
                      f"stage={f['stage']}, error={f.get('error', 'N/A')[:80]}")
        else:
            print("No recent failures.")

    if args.stuck:
        stuck = get_stuck_runs()
        if stuck:
            print(f"Stuck runs ({len(stuck)}):")
            for s in stuck:
                print(f"  {s['pipeline_id']} — started at {s.get('start_time')}")
        else:
            print("No stuck runs detected.")

    if args.missed:
        missed = detect_missed_runs()
        if missed:
            print(f"Missed runs detected ({len(missed)}):")
            for m in missed:
                print(f"  [{m['type']}] Expected {m['expected']}, got {m['actual_uploads']} uploads")
        else:
            print("No missed runs detected.")

    if args.retry_list:
        eligible = get_failed_runs_for_retry()
        if eligible:
            print(f"Runs eligible for retry ({len(eligible)}):")
            for r in eligible:
                cmd = get_recovery_command(r)
                print(f"  {r['pipeline_id']} — retry #{r['retry_count']}/{MAX_RETRIES_PER_RUN}")
                if cmd:
                    print(f"    Command: {cmd}")
        else:
            print("No runs eligible for retry.")
