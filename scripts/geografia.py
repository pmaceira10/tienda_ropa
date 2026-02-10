# geografia.py  (4 tiendas + anticipación Bizkaia, misma estructura)
# Autor: proyecto "ropa"
# Objetivo: generar pesos provinciales (clientes ONLINE) mes a mes con:
#   - Ponderaciones base por CCAA y provincia
#   - Interpolación 2017→2025 con deriva mensual ligera
#   - Reducción sostenida del peso online en provincias con tienda física
#   - Redistribución del peso perdido (anillo CCAA + anillo país) con perturbaciones
#   - Aleatoriedad en *todas* las fases, pero reproducible vía PROJECT_SEED
#   - Sumas y límites garantizados (suelo por provincia y renormalización)

from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime as _dt
from typing import Dict, Tuple, Optional, Any
import math, hashlib
import numbers


# 0) Parámetros globales

PROJECT_START = date(2017, 8, 1)
PROJECT_END   = date(2025, 9, 30)  # inclusive
PROJECT_SEED  = "ropa:v4.4"  # cambia para otra simulación

# Amplitudes de aleatoriedad (pueden afinarse)
BASE_JITTER_PROV   = 0.02   # ±2% multiplicativo sobre pesos intra-CCAA
ANCHOR_JITTER_CCAA = 0.03   # ±3% multiplicativo sobre anclas 2017/2025
MONTHLY_DRIFT_PROV = 0.008  # ±0.8% multiplicativo por provincia/mes
SPLIT_CCAA_MEAN, SPLIT_CCAA_WIDTH = 0.65, 0.10  # 65% ±5% (width/2)
PERTURB_WITHIN_RING = 0.05  # ±5% de perturbación relativa al peso base del receptor

# Suelo/techo relativos al *peso previo a reducciones* del mes
FLOOR_RATIO = 0.35
CEIL_RATIO  = 1.80

# Reducción sostenida por provincia con tienda (fija, sin aleatoriedad)
# >>> AJUSTADO a 4 tiendas (2022–2025)
REDUCCION_PROVINCIA: Dict[str, float] = {
    "Madrid":    0.28,
    "Barcelona": 0.30,
    "Valencia":  0.26,
    "Sevilla":   0.24,
}


# 1) Pesos provinciales base (intra-CCAA). Cada CCAA suma 1.0

PESOS_PROVINCIAS_BASE: Dict[str, Dict[str, float]] = {
    "Andalucía": {
        "Almería": 0.07, "Cádiz": 0.11, "Córdoba": 0.09, "Granada": 0.11,
        "Huelva": 0.06, "Jaén": 0.07, "Málaga": 0.24, "Sevilla": 0.25
    },
    "Aragón": {"Huesca": 0.12, "Teruel": 0.08, "Zaragoza": 0.80},
    "Asturias": {"Asturias": 1.0},
    "Baleares": {"Islas Baleares": 1.0},
    "Canarias": {"Las Palmas": 0.55, "Santa Cruz de Tenerife": 0.45},
    "Cantabria": {"Cantabria": 1.0},
    "Castilla y León": {
        "Ávila": 0.06, "Burgos": 0.12, "León": 0.16, "Palencia": 0.06,
        "Salamanca": 0.11, "Segovia": 0.06, "Soria": 0.04, "Valladolid": 0.28,
        "Zamora": 0.11
    },
    "Castilla-La Mancha": {
        "Albacete": 0.18, "Ciudad Real": 0.20, "Cuenca": 0.10,
        "Guadalajara": 0.12, "Toledo": 0.40
    },
    "Cataluña": {"Barcelona": 0.73, "Girona": 0.10, "Lleida": 0.06, "Tarragona": 0.11},
    "Comunidad Valenciana": {"Alicante": 0.28, "Castellón": 0.10, "Valencia": 0.62},
    "Extremadura": {"Badajoz": 0.60, "Cáceres": 0.40},
    "Galicia": {"A Coruña": 0.40, "Lugo": 0.13, "Ourense": 0.14, "Pontevedra": 0.33},
    "Madrid": {"Madrid": 1.0},
    "Murcia": {"Murcia": 1.0},
    "Navarra": {"Navarra": 1.0},
    "País Vasco": {"Álava": 0.19, "Bizkaia": 0.52, "Gipuzkoa": 0.29},
    "La Rioja": {"La Rioja": 1.0},
    "Ceuta": {"Ceuta": 1.0},
    "Melilla": {"Melilla": 1.0},
}


# 2) Ponderación CCAA (anclas 2017 vs 2025) — se normalizan a 1.0

PESOS_CCAA_ANCLA_2017: Dict[str, float] = {
    "Madrid": 0.70, "Cataluña": 0.08, "Comunidad Valenciana": 0.05, "Andalucía": 0.05,
    "País Vasco": 0.03, "Galicia": 0.02, "Aragón": 0.01, "Castilla y León": 0.01,
    "Castilla-La Mancha": 0.01, "Baleares": 0.01, "Canarias": 0.01, "Murcia": 0.01,
    "Asturias": 0.0038, "Navarra": 0.0024, "Cantabria": 0.0024, "La Rioja": 0.0004,
    "Ceuta": 0.0005, "Melilla": 0.0005, "Extremadura": 0.005,
}
PESOS_CCAA_ANCLA_2025: Dict[str, float] = {
    "Madrid": 0.20, "Cataluña": 0.17, "Andalucía": 0.16, "Comunidad Valenciana": 0.12,
    "País Vasco": 0.06, "Galicia": 0.05, "Aragón": 0.03, "Castilla y León": 0.04,
    "Castilla-La Mancha": 0.03, "Murcia": 0.03, "Canarias": 0.03, "Baleares": 0.03,
    "Asturias": 0.02, "Navarra": 0.0115, "Cantabria": 0.01, "La Rioja": 0.0045,
    "Ceuta": 0.002, "Melilla": 0.002, "Extremadura": 0.01,
}


# 3) Tiendas físicas: fechas de apertura por provincia (YYYY-MM-DD)
#     >>> AJUSTADO a 4 tiendas (retraso primera apertura a 2022)

TIENDAS_FISICAS: Dict[str, str] = {
    "Madrid":    "2022-05-15",
    "Barcelona": "2023-04-01",
    "Valencia":  "2024-03-15",
    "Sevilla":   "2025-03-10",
}


# 3.1) Provincias con anticipación (sin tienda): crecimiento 2024–2025
#       Rampa mensual dentro del año (ene→dic)

CRECIMIENTO_PRE_APERTURA: Dict[str, Dict[int, float]] = {
    # Anticipación norte (Bizkaia) solicitada
    "Bizkaia":    {2024: 1.06, 2025: 1.10},
    # Ejemplos previos, mantenidos pero más suaves
    "Alicante":   {2024: 1.05, 2025: 1.08},
    "Valladolid": {2024: 1.04, 2025: 1.06},
}


# Utilidades de aleatoriedad determinista


def _hash_to_float01(key: str) -> float:
    h = hashlib.sha256((PROJECT_SEED + "|" + key).encode("utf-8")).digest()
    n = int.from_bytes(h[:8], "big")
    return (n & ((1 << 53) - 1)) / float(1 << 53)  # [0,1)

def _randu(key: str, a: float = 0.0, b: float = 1.0) -> float:
    return a + (b - a) * _hash_to_float01(key)

def _randn(key: str, mean: float = 0.0, sd: float = 1.0) -> float:
    u1 = max(_randu(key + ":u1"), 1e-12)
    u2 = _randu(key + ":u2")
    z = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
    return mean + sd * z

def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

# Inversos y helpers

PROV_TO_CCAA: Dict[str, str] = {}
for ccaa, provs in PESOS_PROVINCIAS_BASE.items():
    for p in provs:
        PROV_TO_CCAA[p] = ccaa

ISLAND_CCAA = {"Canarias", "Baleares"}

def _is_island(ccaa: str) -> bool:
    return ccaa in ISLAND_CCAA


# Anclas CCAA con jitter reproducible y normalización

def _normalize(d: Dict[str, float]) -> Dict[str, float]:
    s = sum(max(v, 0.0) for v in d.values())
    if s <= 0:
        raise ValueError("Normalización fallida: suma <= 0")
    return {k: max(v, 0.0) / s for k, v in d.items()}

def _jitter_dict_mult(d: Dict[str, float], label: str, amp: float) -> Dict[str, float]:
    out = {}
    for k, v in d.items():
        eps = _randu(f"jitter:{label}:{k}", -amp, amp)
        out[k] = v * (1.0 + eps)
    return _normalize(out)

_ANCHOR_CACHE: Dict[str, Dict[str, float]] = {}

def _get_anchor(year_label: str) -> Dict[str, float]:
    cache_key = f"anchor:{year_label}"
    if cache_key in _ANCHOR_CACHE:
        return _ANCHOR_CACHE[cache_key]
    base = PESOS_CCAA_ANCLA_2017 if year_label == "2017" else PESOS_CCAA_ANCLA_2025
    base_norm = _normalize(base)
    jittered = _jitter_dict_mult(base_norm, f"anchor-{year_label}", ANCHOR_JITTER_CCAA)
    _ANCHOR_CACHE[cache_key] = jittered
    return jittered


# Interpolación 2017→2025 con deriva mensual ligera

def _month_index(dt: date) -> Tuple[int, int]:
    return dt.year, dt.month

def _interp_ccaa_weights(dt: date) -> Dict[str, float]:
    total_months = (PROJECT_END.year - PROJECT_START.year) * 12 + (PROJECT_END.month - PROJECT_START.month)
    cur_months = (dt.year - PROJECT_START.year) * 12 + (dt.month - PROJECT_START.month)
    t = _clamp(cur_months / max(total_months, 1), 0.0, 1.0)
    a2017 = _get_anchor("2017")
    a2025 = _get_anchor("2025")
    mix = {k: (1.0 - t) * a2017.get(k, 0.0) + t * a2025.get(k, 0.0) for k in a2017.keys() | a2025.keys()}
    mix = _normalize(mix)
    y, m = _month_index(dt)
    out = {}
    for ccaa, w in mix.items():
        eps = _randu(f"drift-ccaa:{ccaa}:{y:04d}{m:02d}", -MONTHLY_DRIFT_PROV/2, MONTHLY_DRIFT_PROV/2)
        out[ccaa] = w * (1.0 + eps)
    return _normalize(out)


# Pesos intra-CCAA por provincia con jitter base y deriva mensual

def _intra_ccaa_weights(ccaa: str, dt: date) -> Dict[str, float]:
    base = PESOS_PROVINCIAS_BASE[ccaa]
    jittered = {}
    for prov, w in base.items():
        eps = _randu(f"prov-jitter:{prov}", -BASE_JITTER_PROV, BASE_JITTER_PROV)
        jittered[prov] = w * (1.0 + eps)
    jittered = _normalize(jittered)
    y, m = _month_index(dt)
    out = {}
    for prov, w in jittered.items():
        eps = _randu(f"drift-prov:{prov}:{y:04d}{m:02d}", -MONTHLY_DRIFT_PROV/2, MONTHLY_DRIFT_PROV/2)
        out[prov] = w * (1.0 + eps)
    return _normalize(out)


# Growth pre-apertura (rampa dentro del año)

def _apply_pre_open_growth(prov_weights: Dict[str, float], dt: date) -> Dict[str, float]:
    y = dt.year
    scalers: Dict[str, float] = {}
    for prov, plan in CRECIMIENTO_PRE_APERTURA.items():
        if y in plan:
            target = plan[y]
            month_factor = 1.0 + (target - 1.0) * (dt.month - 1) / 11.0
            eps = _randu(f"preopen:{prov}:{y:04d}{dt.month:02d}", -0.01, 0.01)
            scalers[prov] = max(0.0, month_factor * (1.0 + eps))
    if not scalers:
        return prov_weights
    out = prov_weights.copy()
    for prov, s in scalers.items():
        if prov in out:
            out[prov] *= s
    s = sum(out.values())
    if s > 0:
        out = {k: v / s for k, v in out.items()}
    return out


# Aplicación de reducciones por tiendas y redistribución con perturbaciones

def _fecha_apertura(prov: str) -> Optional[date]:
    s = TIENDAS_FISICAS.get(prov)
    if not s:
        return None
    return _dt.strptime(s, "%Y-%m-%d").date()

def _split_ccaa_amount(prov: str, dt: date) -> float:
    y, m = _month_index(dt)
    lo = SPLIT_CCAA_MEAN - SPLIT_CCAA_WIDTH/2
    hi = SPLIT_CCAA_MEAN + SPLIT_CCAA_WIDTH/2
    return _clamp(_randu(f"split:{prov}:{y:04d}{m:02d}", lo, hi), lo, hi)

def _perturb_vector(base: Dict[str, float], label: str) -> Dict[str, float]:
    if not base:
        return {}
    out = {}
    for k, v in base.items():
        eps = _randu(f"ring:{label}:{k}", -PERTURB_WITHIN_RING, PERTURB_WITHIN_RING)
        out[k] = max(0.0, v * (1.0 + eps))
    return _normalize(out)

def _apply_store_reductions(prov_weights: Dict[str, float], dt: date) -> Dict[str, float]:
    current = prov_weights.copy()
    base_intra_by_ccaa = {ccaa: PESOS_PROVINCIAS_BASE[ccaa].copy() for ccaa in PESOS_PROVINCIAS_BASE}
    activos = [p for p in REDUCCION_PROVINCIA.keys() if (_fecha_apertura(p) and _fecha_apertura(p) <= dt)]
    for prov in sorted(activos):
        redu = REDUCCION_PROVINCIA[prov]
        if prov not in current:
            continue
        old = current[prov]
        new = old * (1.0 - redu)
        delta = old - new
        if delta <= 0:
            continue
        current[prov] = new

        ccaa = PROV_TO_CCAA[prov]
        split_ccaa = _split_ccaa_amount(prov, dt)
        amt_ccaa = delta * split_ccaa
        amt_country = delta - amt_ccaa

        rc_ccaa = {q: base_intra_by_ccaa[ccaa][q] for q in base_intra_by_ccaa[ccaa] if q != prov}
        rc_ccaa = _perturb_vector(rc_ccaa, f"{prov}:ccaa:{ccaa}")

        excluded_ccaa = None
        if _is_island(ccaa):
            excluded_ccaa = ("Baleares" if ccaa == "Canarias" else "Canarias")
        rc_country = {q: current[q] for q in current if PROV_TO_CCAA[q] != ccaa and PROV_TO_CCAA[q] != excluded_ccaa}
        rc_country = _perturb_vector(rc_country, f"{prov}:country")

        for dest, w in rc_ccaa.items():
            current[dest] += amt_ccaa * w
        for dest, w in rc_country.items():
            current[dest] += amt_country * w

    return _normalize(current)


# Suelos/techos relativos al peso previo a reducción del mes

def _apply_floor_ceil(current: Dict[str, float], pre_reduce: Dict[str, float]) -> Dict[str, float]:
    out = current.copy()
    for prov in out.keys():
        base = pre_reduce.get(prov, out[prov])
        lo = FLOOR_RATIO * base
        hi = CEIL_RATIO * base
        out[prov] = _clamp(out[prov], lo, hi)
    return _normalize(out)


# API principal

def pesos_online_por_fecha(dt: date) -> Dict[str, float]:
    ccaa_w = _interp_ccaa_weights(dt)
    prov_intra: Dict[str, float] = {}
    for ccaa in PESOS_PROVINCIAS_BASE.keys():
        intra = _intra_ccaa_weights(ccaa, dt)
        for prov, w in intra.items():
            prov_intra[prov] = w * ccaa_w.get(ccaa, 0.0)
    prov_pre_reduce = _apply_pre_open_growth(_normalize(prov_intra), dt)
    prov_post_reduce = _apply_store_reductions(prov_pre_reduce, dt)
    final = _apply_floor_ceil(prov_post_reduce, prov_pre_reduce)
    return final


# asignar_provincia (compat extendida)

def asignar_provincia(*args, **kwargs):
    """
    Firmas soportadas:
      - asignar_provincia(year:int, month_or_period:any, random_state=...) -> (provincia, comunidad)
      - asignar_provincia(cliente_id:any, dt:date|datetime|Timestamp|Period|str|tuple|int) -> (provincia, comunidad)
      - asignar_provincia(cliente_id=..., year=..., month=...) -> (provincia, comunidad)
      - asignar_provincia(period=..., year=..., random_state=...) -> (provincia, comunidad)
    También admite return_only='provincia' para devolver solo el string de provincia.
    """
    cliente_id = kwargs.get("cliente_id")
    random_state = kwargs.get("random_state")
    return_only = kwargs.get("return_only")
    year_kw = kwargs.get("year")
    month_kw = kwargs.get("month")

    def _parse_str_period(s: str) -> Tuple[int, int]:
        s = s.strip()
        for fmt in ("%Y-%m", "%Y/%m", "%Y%m", "%Y-%m-%d", "%Y/%m/%d"):
            try:
                d = _dt.strptime(s, fmt)
                return d.year, d.month
            except Exception:
                pass
        raise TypeError("Formato string de 'period' no reconocido (usa 'YYYY-MM' o similar)")

    def _period_to_ym(p, fallback_year: Optional[int] = None) -> Tuple[int, int]:
        if isinstance(p, numbers.Integral):
            if fallback_year is None and year_kw is None:
                raise TypeError("Si 'period' es mes numérico, pasa también 'year='")
            y = int(fallback_year if fallback_year is not None else year_kw)
            m = int(p)
            return y, m
        if isinstance(p, (tuple, list)) and len(p) == 2:
            return int(p[0]), int(p[1])
        if isinstance(p, str):
            return _parse_str_period(p)
        y = getattr(p, "year", None)
        m = getattr(p, "month", None)
        if y is not None and m is not None:
            return int(y), int(m)
        raise TypeError("No puedo interpretar 'period' para construir la fecha")

    dt: Optional[date] = None
    if len(args) == 2:
        a0, a1 = args
        if isinstance(a0, numbers.Integral):
            if isinstance(a1, numbers.Integral):
                y, m = int(a0), int(a1)
            else:
                y, m = _period_to_ym(a1, fallback_year=int(a0))
            dt = date(y, m, 1)
            if cliente_id is None:
                cliente_id = random_state if random_state is not None else f"{y:04d}{m:02d}"
        else:
            cliente_id = a0 if cliente_id is None else cliente_id
            if isinstance(a1, date):
                dt = a1
            else:
                y, m = _period_to_ym(a1)
                dt = date(y, m, 1)
    else:
        if dt is None and (year_kw is not None and month_kw is not None):
            dt = date(int(year_kw), int(month_kw), 1)
        if dt is None and "dt" in kwargs and isinstance(kwargs["dt"], date):
            dt = kwargs["dt"]
        if dt is None and "period" in kwargs:
            y, m = _period_to_ym(kwargs["period"])
            dt = date(y, m, 1)
        if dt is None:
            raise TypeError("Debes proporcionar (year, month) o una fecha 'dt' o 'period'")
        if cliente_id is None:
            cliente_id = random_state if random_state is not None else f"{dt.year:04d}{dt.month:02d}"

    key_id = random_state if random_state is not None else cliente_id
    if key_id is None:
        key_id = "anon"

    weights = pesos_online_por_fecha(dt)
    items = sorted(weights.items())
    u = _randu(f"pick:{key_id}:{dt.year:04d}{dt.month:02d}")

    cum = 0.0
    prov_sel = items[-1][0]
    for prov, w in items:
        cum += w
        if u <= cum:
            prov_sel = prov
            break
    ccaa_sel = PROV_TO_CCAA[prov_sel]

    if return_only == 'provincia':
        return prov_sel
    return prov_sel, ccaa_sel


# Validaciones/debug

def resumen_mes(dt: date) -> Dict[str, Any]:
    ccaa = _interp_ccaa_weights(dt)
    pre = {}
    for c in PESOS_PROVINCIAS_BASE:
        intra = _intra_ccaa_weights(c, dt)
        for p, w in intra.items():
            pre[p] = w * ccaa.get(c, 0.0)
    pre = _apply_pre_open_growth(_normalize(pre), dt)
    post = _apply_store_reductions(pre, dt)
    final = _apply_floor_ceil(post, pre)

    suma = sum(final.values())
    activos = [p for p in REDUCCION_PROVINCIA if (_fecha_apertura(p) and _fecha_apertura(p) <= dt)]
    return {
        "fecha": dt.isoformat(),
        "suma": round(suma, 6),
        "n_provincias": len(final),
        "tiendas_activas": activos,
        "top10": sorted(final.items(), key=lambda kv: kv[1], reverse=True)[:10],
    }

if __name__ == "__main__":
    for y, m in [(2018, 11), (2019, 6), (2020, 3), (2021, 10), (2022, 5), (2023, 6), (2024, 11), (2025, 4)]:
        dt = date(y, m, 1)
        print(resumen_mes(dt))
