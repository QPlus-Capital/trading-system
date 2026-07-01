# Live configurations

Configuration files for running strategies in **live** (and paper) mode.

Only strategies that have been backtested and **approved** get a config here — this
folder is the source of truth for "what is live". The strategy code is the same class
in `src/qplus/strategies/`; promotion to live means adding its config here, never
duplicating or forking the strategy logic.
