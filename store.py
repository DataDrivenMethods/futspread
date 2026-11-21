"""On-disk layout.

    <root>/raw/contracts.parquet          contract metadata for the universe
    <root>/raw/prices/<contrcode>.parquet daily bars, all contracts of a series
    <root>/combos/<TICKER>/<safe>.parquet every instance of one combo, stacked

The raw tree is written once by the downloader; everything downstream reads
the combos tree, which is small enough to load on the fly.  Anything derived
(caches, runs, reports) goes under $FUTSPREAD_OUTPUT, default
<repo>/output, so the data root holds data only.
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

DEFAULT_ROOT = Path(os.environ.get(
    'FUTSPREAD_ROOT', Path.home() / 'futspread_data'))


# Derived files (scan caches, runs, reports) live in the repo, never in the data root.
OUTPUT_ROOT = Path(os.environ.get(
    'FUTSPREAD_OUTPUT', Path(__file__).resolve().parent / 'output'))


def output_path(*parts) -> Path:
    return OUTPUT_ROOT.joinpath(*parts)


def root_path(root=None) -> Path:
    return Path(root) if root is not None else DEFAULT_ROOT


def contracts_path(root=None) -> Path:
    return root_path(root) / 'raw' / 'contracts.parquet'


def liquidity_path(root=None) -> Path:
    return root_path(root) / 'raw' / 'liquidity.parquet'


def series_path(root=None) -> Path:
    return root_path(root) / 'raw' / 'series.parquet'


def prices_path(contrcode: int, root=None) -> Path:
    return root_path(root) / 'raw' / 'prices' / f'{int(contrcode)}.parquet'


def combo_path(spec, root=None) -> Path:
    return (root_path(root) / 'combos' / spec.ticker.upper()
            / f'{spec.safe_code}.parquet')


def write(df: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    return path


def read(path: Path) -> pd.DataFrame:
    if not Path(path).exists():
        raise FileNotFoundError(
            f'{path} not found - run the downloader / builder first')
    return pd.read_parquet(path)
