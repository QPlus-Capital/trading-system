"""Parameter sweep for RsiWprBb on real GBPUSD H4 data (The Trading Pit)."""

from qplus.backtest.recipe_factory import SweepRecipe
from qplus.instruments import gbpusd_ttp

_R = SweepRecipe(gbpusd_ttp(), "data/GBPUSD_H4.csv", leverage=50.0)

INSTRUMENT = _R.INSTRUMENT
CATALOG_PATH = _R.CATALOG_PATH
CSV_PATH = _R.CSV_PATH
OUT_PATH = _R.OUT_PATH
VENUE = _R.VENUE
PARAM_GRID = _R.PARAM_GRID
seed_catalog = _R.seed_catalog
build_run_config = _R.build_run_config
