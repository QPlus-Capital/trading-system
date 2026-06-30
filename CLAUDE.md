# CLAUDE.md – Projektkontext für QPlus Capital

Dieser Hinweis richtet sich an künftige Claude-Code-Sitzungen.

## Zweck

Repository für das **quantitative Handelssystem von QPlus Capital**. Es betreibt
[NautilusTrader](https://nautilustrader.io/) für **Backtesting** auf historischen
Daten und für **Live-Trading**.

## Stack

- **Python 3.13**
- **uv** zur Paket- und Umgebungsverwaltung
- **NautilusTrader** als Engine (Backtest + Live)
- **IBKR** (Interactive Brokers) als Broker und Datenquelle

## Paketstruktur

- `src/qplus/strategies/` – Handelsstrategien
- `src/qplus/backtest/` – Backtest-Konfiguration und -Runner
- `src/qplus/data_ingest/` – Datenbeschaffung & Aufbereitung (IBKR -> Catalog)
- `notebooks/` – Research-Notebooks
- `data/` – Marktdaten / Parquet-Catalog (gitignored)

## ⚠️ Plattform-Einschränkung: Intel-Mac (x86_64)

Die lokale Entwicklungsmaschine ist ein **Intel-Mac (x86_64)**. Für diese
Plattform gibt es **kein `nautilus_trader`-Wheel**.

**Daher NICHT:**
- `nautilus_trader` lokal installieren, importieren oder ausführen
- `uv sync` mit dem Ziel ausführen, NautilusTrader lokal lauffähig zu machen
- den `nautilus_trader`-Eintrag in `pyproject.toml` verändern (unangetastet lassen)

NautilusTrader läuft auf dieser Maschine ausschließlich über das offizielle
Docker-Image `ghcr.io/nautechsystems/jupyterlab:nightly`. Lokal werden nur
Struktur, Code und Dateien gepflegt.

## Prinzip: Code rein, Daten und Secrets raus

- **Code** wird versioniert.
- **Daten** gehören in `data/` (bzw. `catalog/`) und werden **nie** committet.
- **Secrets** gehören in `.env` (Vorlage: `.env.example`) und werden **nie**
  committet.

Beim Hinzufügen neuer Dateien stets prüfen, dass weder Marktdaten noch Secrets
in einen Commit gelangen.
