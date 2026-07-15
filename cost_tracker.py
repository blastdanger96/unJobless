import json
import os
import tempfile
from datetime import date
from threading import Lock


class CostTracker:
    DAILY_LIMIT_USD = float(os.getenv("DAILY_COST_LIMIT", "5.0"))
    MONTHLY_LIMIT_USD = float(os.getenv("MONTHLY_COST_LIMIT", "50.0"))

    PRICING = {
        "gpt-4o-mini": {"in": 0.00015, "out": 0.00060},
        "gpt-4o": {"in": 0.005, "out": 0.015},
    }

    def __init__(self, storage_path: str = "cost_data.json"):
        self.storage_path = storage_path
        self._lock = Lock()
        self._load()

    def _load(self):
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path) as f:
                    data = json.load(f)
            except json.JSONDecodeError:
                data = {}
            self.daily_spend = data.get("daily_spend", 0.0)
            self.monthly_spend = data.get("monthly_spend", 0.0)
            self.last_day = data.get("last_day")
            self.last_month = data.get("last_month")
        else:
            self.daily_spend = 0.0
            self.monthly_spend = 0.0
            self.last_day = str(date.today())
            self.last_month = str(date.today().replace(day=1))

    def _save(self):
        with self._lock:
            # Atomic write: write to temp file then rename
            dir_name = os.path.dirname(self.storage_path) or "."
            with tempfile.NamedTemporaryFile(
                mode="w", dir=dir_name, delete=False, suffix=".tmp"
            ) as tmp:
                json.dump({
                    "daily_spend": self.daily_spend,
                    "monthly_spend": self.monthly_spend,
                    "last_day": self.last_day,
                    "last_month": self.last_month,
                }, tmp)
                tmp_path = tmp.name
            os.replace(tmp_path, self.storage_path)

    def _reset_if_new_period(self):
        today = str(date.today())
        this_month = str(date.today().replace(day=1))
        if today != self.last_day:
            self.daily_spend = 0.0
            self.last_day = today
        if this_month != self.last_month:
            self.monthly_spend = 0.0
            self.last_month = this_month

    def record(self, model: str, tokens_in: int, tokens_out: int) -> bool:
        self._reset_if_new_period()

        pricing = self.PRICING.get(model, self.PRICING["gpt-4o-mini"])
        cost = (tokens_in / 1000) * pricing["in"] + (tokens_out / 1000) * pricing["out"]

        self.daily_spend += cost
        self.monthly_spend += cost
        self._save()

        return (self.daily_spend <= self.DAILY_LIMIT_USD and
                self.monthly_spend <= self.MONTHLY_LIMIT_USD)

    def get_status(self) -> dict:
        self._reset_if_new_period()
        return {
            "daily_usd": round(self.daily_spend, 4),
            "monthly_usd": round(self.monthly_spend, 4),
            "daily_limit_usd": self.DAILY_LIMIT_USD,
            "monthly_limit_usd": self.MONTHLY_LIMIT_USD,
            "daily_remaining_usd": round(max(0, self.DAILY_LIMIT_USD - self.daily_spend), 4),
            "monthly_remaining_usd": round(max(0, self.MONTHLY_LIMIT_USD - self.monthly_spend), 4),
            "over_daily": self.daily_spend > self.DAILY_LIMIT_USD,
            "over_monthly": self.monthly_spend > self.MONTHLY_LIMIT_USD,
        }


_tracker = CostTracker()


def get_cost_tracker() -> CostTracker:
    return _tracker