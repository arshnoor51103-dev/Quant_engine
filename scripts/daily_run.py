"""
Entry point for the scheduled daily run.

Called by scripts/daily_run.bat (Windows Task Scheduler).
Reads daily_run config from config/portfolio.yaml.
Writes to logs/YYYY-MM-DD.log (appended).
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from src.cli.daily_run_command import DailyRunner
from src.portfolio.model import load_portfolio_config


def main() -> int:
    cfg = load_portfolio_config()
    dr_cfg = cfg.get("daily_run", {})
    log_path = _PROJECT_ROOT / "logs" / f"{date.today()}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with DailyRunner(
        log_target=log_path,
        default_cash=float(dr_cfg.get("default_cash", 0.0)),
        step_timeout_seconds=int(dr_cfg.get("step_timeout_seconds", 300)),
    ) as runner:
        return runner.run()


if __name__ == "__main__":
    sys.exit(main())
