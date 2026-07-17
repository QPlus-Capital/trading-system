# Backtest configurations

Configuration files for running strategies in **backtest** mode (historical data).

A strategy's code lives once in `src/qplus/strategies/`. A file here wires that
strategy to backtest parameters (instruments, date range, data source, sizing, etc.).
Backtesting a strategy never requires changing its code — only a config here.
