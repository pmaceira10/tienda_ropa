from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, Iterable, Optional, Tuple
import hashlib
import math


PROJECT_START = date(2017, 8, 1)
PROJECT_END = date(2025, 9, 30)


def month_iter(start: date, end: date) -> Iterable[Tuple[int, int]]:
    """Itera (year, month) desde start hasta end (inclusive por mes)."""
    y, m = start.year, start.month
    while (y < end.year) or (y == end.year and m <= end.month):
        yield y, m
        m += 1
        if m == 13:
            y += 1
            m = 1


def days_in_month(year: int, month: int) -> int:
    """Devuelve el número de días del mes."""
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    return (next_month - timedelta(days=1)).day


def stable_int_seed(*parts: str, mod: int = 2_147_483_647) -> int:
    """
    Crea una semilla entera estable a partir de partes de texto.
    """
    h = hashlib.sha256("||".join(parts).encode("utf-8")).hexdigest()
    return int(h[:15], 16) % mod


class SimpleLCG:
    """
    PRNG determinista (Park–Miller / MINSTD). Suficiente para sampling reproducible.
    """
    def __init__(self, seed: int):
        self.state = (seed % 2_147_483_647) or 1

    def rand(self) -> float:
        a = 48271
        m = 2_147_483_647
        self.state = (a * self.state) % m
        return self.state / m

    def randint(self, low: int, high: int) -> int:
        """Entero en [low, high], ambos inclusive."""
        if low > high:
            raise ValueError("low > high en randint")
        span = high - low + 1
        return low + int(math.floor(self.rand() * span))


@dataclass(frozen=True)
class DateOverrides:
    """
    Overrides por periodo 'YYYY-MM' a un día fijo (1..n_días).
    """
    by_period_day: Dict[str, int]

    def get_fixed_day(self, year: int, month: int) -> Optional[int]:
        return self.by_period_day.get(f"{year:04d}-{month:02d}")


def sample_random_day_in_month(
    year: int,
    month: int,
    *,
    base_seed: str = "global",
    period_scope: str = "cohort",
    unique_key: Optional[str] = None,
    overrides: Optional[DateOverrides] = None,
    allowed_days: Optional[Iterable[int]] = None,
) -> date:
    """
    Devuelve una fecha dentro del mes.
    Si existe override para 'YYYY-MM', usa ese día. Si no, muestrea un día de forma determinista.
    """
    dim = days_in_month(year, month)

    if overrides is not None:
        fixed = overrides.get_fixed_day(year, month)
        if fixed is not None:
            d = min(max(1, fixed), dim)
            return date(year, month, d)

    seed_parts = [base_seed, period_scope, f"{year:04d}-{month:02d}"]
    if unique_key is not None:
        seed_parts.append(str(unique_key))
    rng = SimpleLCG(stable_int_seed(*seed_parts))

    if allowed_days is not None:
        pool = sorted(d for d in allowed_days if 1 <= d <= dim)
        if not pool:
            raise ValueError("allowed_days no contiene días válidos para este mes.")
        idx = rng.randint(0, len(pool) - 1)
        return date(year, month, pool[idx])

    return date(year, month, rng.randint(1, dim))


def build_project_months(start: date = PROJECT_START, end: date = PROJECT_END):
    """
    Devuelve una lista de dicts con metadatos por mes del proyecto.
    """
    out = []
    for y, m in month_iter(start, end):
        dim = days_in_month(y, m)
        out.append(
            {
                "year": y,
                "month": m,
                "period": f"{y:04d}-{m:02d}",
                "days_in_month": dim,
                "month_start": date(y, m, 1),
                "month_end": date(y, m, dim),
            }
        )
    return out


def _nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> int:
    """
    Día (1..31) del n-ésimo weekday del mes.
    weekday: Monday=0 ... Sunday=6.
    """
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    day = 1 + offset + 7 * (n - 1)
    dim = days_in_month(year, month)
    if day > dim:
        raise ValueError("El n-ésimo weekday no existe en este mes.")
    return day


def black_friday_day(year: int) -> int:
    """Black Friday: 4º viernes de noviembre."""
    FRIDAY = 4
    return _nth_weekday_of_month(year, 11, FRIDAY, 4)


def build_default_overrides(start: date = PROJECT_START, end: date = PROJECT_END) -> DateOverrides:
    """
    Overrides por defecto del proyecto.
    Actualmente fija Black Friday (noviembre) para todos los años del rango.
    """
    by_period = {}
    for y, m in month_iter(start, end):
        if m == 11:
            by_period[f"{y:04d}-{m:02d}"] = black_friday_day(y)
    return DateOverrides(by_period)


DEFAULT_OVERRIDES = build_default_overrides()

