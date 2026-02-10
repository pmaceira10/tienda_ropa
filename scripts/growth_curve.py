from dataclasses import dataclass
from typing import Dict, List
import math

from calendario import (
    build_project_months,
    PROJECT_START,
    PROJECT_END,
    stable_int_seed,
    SimpleLCG,
    DEFAULT_OVERRIDES,
    black_friday_day,
)

@dataclass(frozen=True)
class Seasonality:
    by_month: Dict[int, float]

DEFAULT_SEASONALITY = Seasonality({
    1: 1.15,
    7: 1.20,
    8: 0.85,
    11: 1.38,
    12: 1.25,
})

@dataclass(frozen=True)
class GrowthConfig:
    targets_by_year: Dict[int, int]
    seasonality: Seasonality = DEFAULT_SEASONALITY

def _logistic_index(n: int, k: float = 6.0) -> List[float]:
    xs = [(-3.0 + 6.0 * (i / max(1, n - 1))) for i in range(n)]
    vals = [1.0 / (1.0 + math.exp(-k * x / 6.0)) for x in xs]
    mean = sum(vals) / n
    return [v / mean for v in vals]

def _day_weights_for_month(year: int, month: int, dim: int) -> List[float]:
    """
    Pesos diarios (media 1.0) para sesgar la distribución intra-mes.
    Rebajas: impulso fuerte al inicio y decaimiento posterior, manteniéndose por encima del baseline.
    Black Friday: pico en el día exacto con halo corto.
    Diciembre: refuerzo 10–24 y final de mes.
    """
    rng = SimpleLCG(stable_int_seed("day-bias", f"{year:04d}-{month:02d}"))
    w = [1.0 for _ in range(dim)]

    for i in range(dim):
        w[i] *= 1.0 + (rng.rand() * 0.10 - 0.05)

    if month == 1:
        start = min(7, dim)
        length = min(14, max(1, dim - start + 1))
        bump = 1.10 + rng.rand() * 0.25
        for d in range(start, start + length):
            dist = d - start
            decay = 1.0 - 0.30 * (dist / (length - 1 + 1e-9))
            w[d - 1] *= bump * max(0.80, decay)

    if month == 7:
        length = min(10, dim)
        bump = 1.10 + rng.rand() * 0.20
        for d in range(1, length + 1):
            dist = d - 1
            decay = 1.0 - 0.25 * (dist / (length - 1 + 1e-9))
            w[d - 1] *= bump * max(0.85, decay)

    if month == 11:
        bf = DEFAULT_OVERRIDES.get_fixed_day(year, 11)
        if bf is None:
            bf = black_friday_day(year)

        if 1 <= bf <= dim:
            spike = 1.80 + rng.rand() * 0.60
            w[bf - 1] *= spike
            for delta in (-3, -2, -1, 1, 2, 3):
                d = bf + delta
                if 1 <= d <= dim:
                    base = 1.10 + (0.20 * (1 - abs(delta) / 3.0))
                    w[d - 1] *= base * (1.0 + (rng.rand() * 0.06 - 0.03))

    if month == 12:
        start, end = 10, min(24, dim)
        bump_mid = 1.10 + rng.rand() * 0.20
        for d in range(start, end + 1):
            w[d - 1] *= bump_mid * (1.0 + (rng.rand() * 0.06 - 0.03))
        for d in range(min(dim, 26), dim + 1):
            w[d - 1] *= 1.05 + rng.rand() * 0.10

    mean = sum(w) / dim if dim > 0 else 1.0
    if mean > 0:
        w = [x / mean for x in w]
    return w

def build_monthly_new_customers(config: GrowthConfig) -> List[dict]:
    months = build_project_months(PROJECT_START, PROJECT_END)
    n = len(months)
    base = _logistic_index(n, k=6.0)

    adjusted = []
    for i, meta in enumerate(months):
        m = meta["month"]
        mult = config.seasonality.by_month.get(m, 1.0)
        rng = SimpleLCG(stable_int_seed("month-noise", meta["period"]))
        mult_noise = 1.0 + (rng.rand() * 0.08 - 0.04)
        adjusted.append(base[i] * mult * mult_noise)

    out = []
    by_year = {}
    for i, meta in enumerate(months):
        by_year.setdefault(meta["year"], []).append((i, adjusted[i]))

    for year, vals in by_year.items():
        target = config.targets_by_year.get(year, 0)

        if target == 0:
            for idx, _ in vals:
                meta = months[idx]
                dim = meta["days_in_month"]
                out.append({
                    "period": meta["period"],
                    "year": meta["year"],
                    "month": meta["month"],
                    "days_in_month": dim,
                    "new_customers": 0,
                    "day_weights": [1.0] * dim,
                })
            continue

        total_raw = sum(v for _, v in vals)
        for idx, v in vals:
            meta = months[idx]
            dim = meta["days_in_month"]
            share = v / total_raw if total_raw > 0 else 0.0
            new_customers = int(round(share * target))

            day_weights = _day_weights_for_month(meta["year"], meta["month"], dim)

            out.append({
                "period": meta["period"],
                "year": meta["year"],
                "month": meta["month"],
                "days_in_month": dim,
                "new_customers": new_customers,
                "day_weights": day_weights,
            })

    return out

def example_config() -> GrowthConfig:
    targets = {
        2017: 2960,
        2018: 7400,
        2019: 17790,
        2020: 16710,
        2021: 28110,
        2022: 39940,
        2023: 42900,
        2024: 53250,
        2025: 39940,
    }
    return GrowthConfig(targets_by_year=targets)

if __name__ == "__main__":
    cfg = example_config()
    rows = build_monthly_new_customers(cfg)
    for r in rows[:3]:
        print(
            r["period"],
            r["month"],
            r["new_customers"],
            "days:",
            r["days_in_month"],
            "sample day_weights:",
            r["day_weights"][:8],
        )
