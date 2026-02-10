# edades.py
from __future__ import annotations
from typing import Dict, Tuple, List, Optional
import numpy as np
import hashlib
from datetime import date

# Tramos y pesos objetivo base (Nude Project-like)
AGE_BUCKETS: List[Tuple[int, int]] = [
    (16, 17),   # idx 0
    (18, 22),   # idx 1
    (23, 28),   # idx 2
    (29, 34),   # idx 3
    (35, 45),   # idx 4
]
TARGET = np.array([0.07, 0.40, 0.35, 0.15, 0.03], dtype=float)

def _rng_from_key(key: str) -> np.random.Generator:
    """RNG determinista por clave (mes/provincia) para reproducibilidad."""
    seed = int(hashlib.sha1(key.encode("utf-8")).hexdigest(), 16) % (2**32 - 1)
    return np.random.default_rng(seed)

def _apply_drift(weights: np.ndarray, base_year: int, current_year: int) -> np.ndarray:
    """
    Drift anual muy leve:
      +0.3 p.p./año al bucket 18–22 (idx 1)
      -0.3 p.p./año compensado al bucket 29–34 (idx 3)
    """
    delta_years = max(0, current_year - base_year)
    drift = 0.003 * delta_years  # 0.3% por año
    w = weights.copy()
    w[1] += drift
    w[3] = max(0.0, w[3] - drift)
    w = np.clip(w, 1e-6, None)
    return w / w.sum()

def _apply_geo_bias(weights: np.ndarray, provincia: Optional[str]) -> np.ndarray:
    """
    Sesgo por provincia (opcional).
    Ejemplo: ciudades universitarias empujan 18–22 un +15% relativo.
    Ajusta o elimina a tu gusto.
    """
    if not provincia:
        return weights
    uni_cities = {"Granada", "Salamanca", "Zaragoza", "Valencia", "Santiago de Compostela"}
    w = weights.copy()
    if provincia in uni_cities:
        boost = 1.15
        w[1] *= boost  # 18–22
    w = np.clip(w, 1e-6, None)
    return w / w.sum()

def sample_weights_for_month(month_key: str,
                             year: int,
                             alpha_total: int = 1000,
                             apply_drift_from_year: int = 2017,
                             provincia: Optional[str] = None) -> np.ndarray:
    """
    Devuelve un vector de probabilidades por bucket para un mes dado.
    - month_key: p.ej. "2019-11"
    - year: año del mes (para drift)
    - alpha_total: concentración Dirichlet (↑ = menos variación)
    """
    rng = _rng_from_key(f"{month_key}|{provincia or ''}")
    alpha = TARGET * float(alpha_total)
    weights = rng.dirichlet(alpha)
    weights = _apply_drift(weights, base_year=apply_drift_from_year, current_year=year)
    weights = _apply_geo_bias(weights, provincia)
    return weights

def sample_age_from_weights(rng: np.random.Generator, weights: np.ndarray) -> int:
    """Elige bucket por Categorical y edad entera uniforme dentro del tramo."""
    idx = rng.choice(len(AGE_BUCKETS), p=weights)
    lo, hi = AGE_BUCKETS[idx]
    return rng.integers(lo, hi + 1)

def build_month_samplers(month_key: str,
                         year: int,
                         provincia: Optional[str] = None) -> Tuple[np.random.Generator, np.ndarray]:
    """RNG determinista + pesos para un (mes, provincia) concreto."""
    rng = _rng_from_key(f"RNG|{month_key}|{provincia or ''}")
    weights = sample_weights_for_month(month_key, year, provincia=provincia)
    return rng, weights
