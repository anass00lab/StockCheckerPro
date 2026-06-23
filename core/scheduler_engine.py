"""
Scheduler engine for Stock Checker Pro.
Manages automated daily/weekly runs using APScheduler.
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.logger import log

_scheduler = None
_stock_check_callback = None
_benchmark_callback = None

DAY_MAP = {
    "Monday": "mon",
    "Tuesday": "tue",
    "Wednesday": "wed",
    "Thursday": "thu",
    "Friday": "fri",
    "Saturday": "sat",
    "Sunday": "sun"
}


def set_callbacks(stock_check_fn, benchmark_fn):
    """Set the functions to call when scheduled runs trigger."""
    global _stock_check_callback, _benchmark_callback
    _stock_check_callback = stock_check_fn
    _benchmark_callback = benchmark_fn


def _run_stock_check():
    """Wrapper called by scheduler for stock check."""
    log(f"Scheduled stock check triggered at {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    if _stock_check_callback:
        try:
            _stock_check_callback()
        except Exception as e:
            log(f"Scheduled stock check error: {e}", "ERROR")


def _run_benchmark():
    """Wrapper called by scheduler for benchmark check."""
    log(f"Scheduled benchmark check triggered at {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    if _benchmark_callback:
        try:
            _benchmark_callback()
        except Exception as e:
            log(f"Scheduled benchmark check error: {e}", "ERROR")


def start_scheduler(schedule_config: dict):
    """
    Start the scheduler with the given configuration.
    schedule_config format:
    {
        "stock_check": {
            "Monday": {"enabled": True, "time": "18:00"},
            ...
        },
        "benchmark": {
            "enabled": True,
            "day": "Monday",
            "time": "08:00"
        }
    }
    """
    global _scheduler

    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)

    _scheduler = BackgroundScheduler()

    # Add stock check jobs
    stock_config = schedule_config.get("stock_check", {})
    for day, config in stock_config.items():
        if config.get("enabled"):
            time_str = config.get("time", "09:00")
            hour, minute = map(int, time_str.split(":"))
            day_abbr = DAY_MAP.get(day, day.lower()[:3])
            _scheduler.add_job(
                _run_stock_check,
                CronTrigger(day_of_week=day_abbr, hour=hour, minute=minute),
                id=f"stock_{day}",
                replace_existing=True,
                misfire_grace_time=3600
            )
            log(f"Scheduled stock check: {day} at {time_str}")

    # Add benchmark job
    bench_config = schedule_config.get("benchmark", {})
    if bench_config.get("enabled"):
        bench_day = bench_config.get("day", "Monday")
        bench_time = bench_config.get("time", "08:00")
        hour, minute = map(int, bench_time.split(":"))
        day_abbr = DAY_MAP.get(bench_day, bench_day.lower()[:3])
        _scheduler.add_job(
            _run_benchmark,
            CronTrigger(day_of_week=day_abbr, hour=hour, minute=minute),
            id="benchmark_weekly",
            replace_existing=True,
            misfire_grace_time=3600
        )
        log(f"Scheduled benchmark check: {bench_day} at {bench_time}")

    _scheduler.start()
    log("Scheduler started successfully")


def stop_scheduler():
    """Stop the scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def get_next_run_times() -> dict:
    """Get the next scheduled run times."""
    if not _scheduler or not _scheduler.running:
        return {}

    result = {}
    for job in _scheduler.get_jobs():
        next_run = job.next_run_time
        if next_run:
            result[job.id] = next_run.strftime("%A %b %d at %I:%M %p")
    return result


def get_next_stock_run() -> str | None:
    """Get the next stock check run time as a display string."""
    if not _scheduler or not _scheduler.running:
        return None

    next_times = []
    for job in _scheduler.get_jobs():
        if job.id.startswith("stock_") and job.next_run_time:
            next_times.append(job.next_run_time)

    if next_times:
        earliest = min(next_times)
        return earliest.strftime("%A %b %d at %I:%M %p")
    return None


def is_running() -> bool:
    """Check if the scheduler is running."""
    return _scheduler is not None and _scheduler.running
