# QPlus Capital – Quantitatives Handelssystem

Quantitatives Handelssystem von **QPlus Capital** auf Basis von
[NautilusTrader](https://nautilustrader.io/). Das System dient sowohl dem
**Backtesting** von Strategien auf historischen Daten als auch dem späteren
**Live-Trading** über einen Broker.

## Tech-Stack

| Komponente        | Verwendung                                            |
| ----------------- | ----------------------------------------------------- |
| **Python 3.13**   | Programmiersprache                                    |
| **uv**            | Paket- und Umgebungsverwaltung                        |
| **NautilusTrader**| Event-getriebene Engine für Backtest & Live-Trading   |
| **IBKR**          | Interactive Brokers als Broker und Datenquelle        |

## Ordnerstruktur

```
trading-system/
├── src/qplus/              # Python-Paket (versionierter Code)
│   ├── strategies/         # Handelsstrategien (NautilusTrader-Strategien)
│   ├── backtest/           # Backtest-Konfiguration und -Runner
│   └── data_ingest/        # Datenbeschaffung & Aufbereitung (z. B. IBKR -> Catalog)
├── notebooks/              # Jupyter-Notebooks für Research & Analyse
├── data/                   # Marktdaten / Parquet-Catalog (NIE versioniert)
├── .env.example            # Vorlage für Secrets (versioniert, nur Platzhalter)
├── .env                    # Echte Secrets (NIE versioniert)
├── pyproject.toml          # Projekt- und Abhängigkeitsdefinition
└── uv.lock                 # Gepinnte Abhängigkeiten
```

## Setup

### (a) Apple Silicon (arm64) oder Linux

Für diese Plattformen existiert ein `nautilus_trader`-Wheel, die Installation
läuft direkt über uv:

```bash
uv sync
```

Anschließend Secrets anlegen:

```bash
cp .env.example .env   # danach echte Werte in .env eintragen
```

### (b) Intel-Mac (x86_64)

**Wichtig:** Für Intel-Macs (x86_64) gibt es **kein** `nautilus_trader`-Wheel —
ein lokales `uv sync` mit NautilusTrader schlägt hier fehl. Stattdessen wird über
das offizielle Docker-Image gearbeitet:

```
ghcr.io/nautechsystems/jupyterlab:nightly
```

Beispiel:

```bash
docker run --rm -it \
  -p 8888:8888 \
  -v "$(pwd)":/workspace \
  -w /workspace \
  ghcr.io/nautechsystems/jupyterlab:nightly
```

Damit steht eine JupyterLab-Umgebung mit vorinstalliertem NautilusTrader zur
Verfügung; das Repository wird per Volume eingehängt, sodass `src/qplus/`,
`notebooks/` und `data/` direkt nutzbar sind.

## Prinzip: Code rein, Daten und Secrets raus

- **Code** wird versioniert (alles unter `src/qplus/`, `notebooks/`).
- **Marktdaten** gehören in `data/` (bzw. `catalog/`) und werden **nie**
  committet — beide sind via `.gitignore` ausgeschlossen.
- **Secrets** (IBKR-Zugangsdaten o. Ä.) gehören in `.env` und werden **nie**
  committet. Als Vorlage dient die versionierte `.env.example` mit reinen
  Platzhaltern.
