"""Parameter sweep for RsiWprBb on real DE40 (DAX) H4 data (The Trading Pit).

Note: DE40 is EUR-settled but modelled USD-quoted for now (see instruments.py).
"""

from qplus.backtest.recipe_factory import SweepRecipe
from qplus.instruments import de40_ttp

_R = SweepRecipe(de40_ttp(), "data/DE40_H4.csv", leverage=15.0)

INSTRUMENT = _R.INSTRUMENT
CATALOG_PATH = _R.CATALOG_PATH
CSV_PATH = _R.CSV_PATH
OUT_PATH = _R.OUT_PATH
VENUE = _R.VENUE
PARAM_GRID = _R.PARAM_GRID
seed_catalog = _R.seed_catalog
build_run_config = _R.build_run_config
