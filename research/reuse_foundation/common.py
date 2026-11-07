"""Canonical serialization and access to the unchanged stage-two contracts."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np


def packed(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode()).hexdigest()


_path = Path(__file__).resolve().parents[1] / 'ChatGPT/总体计划执行-v1/阶段二/framework.py'
_name = '_sera_frozen_stage2'
if _name not in sys.modules:
    _spec = importlib.util.spec_from_file_location(_name, _path)
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[_name] = _module
    _spec.loader.exec_module(_module)
framework = sys.modules[_name]
Ledger, Exhausted = framework.Ledger, framework.Exhausted
SCORE, canonical = framework.SCORE, framework.canonical


def normalized(vector, dtype):
    if dtype not in ('float32', 'float64'):
        raise ValueError('explicit float32 or float64 input dtype required')
    raw = np.asarray(vector, dtype=np.dtype(dtype).newbyteorder('<'))
    if raw.ndim != 1 or not len(raw) or not np.isfinite(raw).all():
        raise ValueError('finite one-dimensional vector required')
    norm = np.linalg.norm(raw.astype(np.float64))
    if norm == 0 or not np.isfinite(norm):
        raise ValueError('zero or invalid vector norm')
    out = raw.astype(np.float64)
    if dtype == 'float32':
        out /= norm
    elif abs(norm - 1) > 1e-8:
        raise ValueError('float64 input must already satisfy the canonical contract')
    return out, digest(raw.tobytes())
