"""Data acquisition & preparation (into the NautilusTrader Parquet catalog)."""

from qplus.data_ingest.synthetic import make_synthetic_bars, write_synthetic_catalog

__all__ = ["make_synthetic_bars", "write_synthetic_catalog"]
