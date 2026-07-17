# Repo-Review 2026-07 — Lesepfad & Findings

> **Temporäres Arbeitsdokument** für Jans Solo-Review (Phase 1 des Cleanups).
> Bewusst auf Deutsch — wird vor dem Merge des `cleanup`-Branches gelöscht bzw.
> in Issues/Commits überführt. (Ausnahme von der Englisch-Regel, absichtlich.)

## Wie du vorgehst

1. Erst [architecture.md](architecture.md) lesen — die Schaubilder sind deine Karte.
2. Dann die Module in der Reihenfolge unten. **Alles** notieren, auch „versteh ich
   nicht" — schlechte Verständlichkeit ist ein Doku-Bug, kein Leser-Fehler.
3. Jede Notiz in eine der Kategorien am Ende eintragen, mit `datei.py:zeile` wenn
   möglich. Nicht lange formulieren — Stichpunkte reichen, wir arbeiten sie
   gemeinsam ab.

Leitfragen bei jedem Modul:

- Verstehe ich in 2 Minuten, **was** die Datei tut und **warum** es sie gibt?
- Passt der Name (Datei, Funktionen, Begriffe) zu dem, was wirklich passiert?
- Würde ich die Datei woanders einsortieren? Gehören Dinge zusammen, die getrennt
  sind (oder umgekehrt)?
- Gibt es Code/Kommentare, die veraltet wirken oder auf Altlasten verweisen?
- Traue ich der Logik? (Bei Zweifel: als *Frage* notieren, nicht selbst grübeln.)

## Lesepfad (vom Konzept zum Detail)

### Block A — Das Fundament (~30 min)
- [Paper Trading kann raus; Viel zu spezifisch es soll da nicht drin stehen das zum beispiel auf H4 gehandelt wird weil das ist ja nur eine strategie und die readme soll ja allgemein gelten; metatrader auch zu spezfisich wir legen uns ja nicht nur darauf fest; dateistruktur muss komplett angepasst werden wie schon in den kommentaren zur architektur erwähnt; die notizen hier gelten auch für alle anderen dateien die eig allgemein sein sollen aber spezifisch sind ] `README.md` — stimmt die Beschreibung noch mit der Realität überein?
- [ ] `RUN.md` — könnte ein Fremder damit das System starten?
- [ ] `CLAUDE.md` — sind die Regeln vollständig und aktuell?
- [ ] `docs/methodology.md` — die Spezifikation. Deckt sie sich mit dem Code?
- [ ] `docs/live-runbook.md`, `docs/roadmap.md` — was davon ist noch wahr, was ist
      Museum? (`mt5-bridge-plan.md` ist bereits gelöscht — Plan war komplett umgesetzt.)

### Block B — Der Strategie-Kern (~20 min)
- [ ] `strategies/rsi_wpr_bb_signals.py` — DIE zentrale Datei (backtest == live)
- [ ] `strategies/rsi_wpr_bb.py` — nur dünner Nautilus-Mantel?
- [ ] `docs/strategies/rsi_wpr_bb.md`

### Block C — Research-Pipeline in Ausführungsreihenfolge (~60–90 min)
- [ ] `data_ingest/mt5_csv.py`, `instruments.py`, `backtest/broker.py`
- [ ] `backtest/foundation/` — recipe → grid → montecarlo → overfitting → trial_budget
- [ ] `backtest/edge/` — walkforward → engine → characterize
- [ ] `config/study/robustness.py` — die Studien-Definition
- [ ] `backtest/stages/` — edge → select → portfolio → verdict (+ `_runbook`, `pipeline.py`)
- [ ] `backtest/select/universe.py`
- [ ] `backtest/portfolio/` — trades → curves → sizing → risk → tail → stress →
      factsheet → html_report/report → regime/correlation
- [ ] `backtest/portfolio/equity_report.py`, `swap_analysis.py` — Standalone-Tools:
      behalten, umbauen oder löschen?

### Block D — Live-Pfad (echtes Geld, hier besonders kritisch lesen) (~45 min)
- [ ] `live/run.py` → `accounts.py` → `mt5_bridge.py` → `runner.py`
- [ ] `live/risk_control.py` — die Limits, die dein Konto schützen
- [ ] `live/preflight.py`, `parity_check.py`, `notify.py`
- [ ] `config/live/paper_rsi_wpr_bb.py` — der eingefrorene Live-Config

### Block E — Monitoring + Tests + Config (~30 min)
- [ ] `monitoring/` — dashboard, live, reference, research
- [ ] `tests/` — Stichproben: sagen die Testnamen, was geprüft wird? Fehlt dir etwas?
- [ ] `config/backtest/`, `config/broker/` — noch alles in Benutzung?
- [ ] `pyproject.toml` — Abhängigkeiten, Tool-Konfiguration

## Findings

### Unklar (verstehe ich nicht / Doku fehlt)
- [ ] …

### Falsch (vermuteter Fehler / verdächtige Logik)
- [ ] …

### Umbenennen / Verschieben (Struktur & Namen)
- [ ] …

### Löschen (Altlast / tot / Museum)
- [ ] …

### Frage an Claude (gemeinsam klären)
- [ ] …

### Idee (kein Fehler, aber Verbesserung)
- [ ] …

## Bekannte offene Punkte (aus früheren Sessions, zum Abarbeiten in Phase 2)

- `equity_report`/`correlation`/`regime` Standalone-`__main__`s laufen noch auf dem
  alten MEX-Profil (Swap in flat PnL statt `swap_base`-Konvention).
- FX-Kommissionsmodell ist generisch (`_FX 0.00002` ≈ TTPs $2/lot bei EURUSD),
  unterschätzt günstigere FX-Paare — geringer Effekt.
- `ruff format` ist kein Gate: 13 Dateien wären umzuformatieren — einheitlich machen?
- `docs/mt5-bridge-plan.md` und Teile von `docs/roadmap.md` sind vermutlich Museum.

## Überbleibsel-Sweep (Claude, 2026-07-16 — vulture + Import-Analyse)

### A. Klar tot — GELÖSCHT am 2026-07-16 (auf diesem Branch; Git-Historie bewahrt alles)

| Kandidat | Befund |
|---|---|
| ~~`backtest/validation/` (ganzes Paket) + `tests/test_backtest_scorecard.py`~~ | Alte „Scorecard" + alter Stress-Pfad, von der Stages-CLI abgelöst. Null src-Importe. GELÖSCHT. |
| ~~`backtest/portfolio/report.py` + `tests/test_backtest_report.py`~~ | Stage 4 nutzt `html_report`; `plot_monte_carlo` gab es doppelt. GELÖSCHT. |
| ~~`curves.load_daily_extremes` + `worst_unrealized` (+ 2 Tests)~~ | Intraday-Adverse-Marking, nie verdrahtet. GELÖSCHT — bei Bedarf als Feature aus der Historie wiederholbar (wäre ein Ehrlichkeits-Upgrade: DD an Tagesextremen statt Schlusskursen messen). |
| ~~`risk.TTP_ACCOUNT`~~ | Nie referenziert (Config liefert `ACCOUNT`). GELÖSCHT. |
| ~~`risk_control.on_close()`~~ | Nie aufgerufen (Open-Risk wird je Zyklus neu berechnet). GELÖSCHT. |
| ~~`factsheet.median_hold_days`~~ | Berechnet, nie gerendert. GELÖSCHT. |
| ~~`drawdown.min_margin_frac`~~ | Gesetzt, nie gelesen. GELÖSCHT. |
| ~~`parity_check.close_diff_mean`~~ | Weder gedruckt noch im Verdict. GELÖSCHT. |
| ~~`docs/mt5-bridge-plan.md`~~ | Plan vollständig umgesetzt. GELÖSCHT (+ RUN.md-Verweise korrigiert: Stages-CLI statt totem `pipeline`-`__main__`, `--account`-Flag). |

### B. Altlast-Pfad „Einzel-Backtest-Ära" — Entscheidung nötig, nicht blind löschen

- `config/backtest/rsi_wpr_bb_xauusd.py` + `sweep_rsi_wpr_bb_xauusd.py`, die
  `__main__`s von `backtest/config.py` und `foundation/grid.py`: der Vor-Framework-Pfad
  (ein Markt, ein Lauf). Noch in RUN.md dokumentiert. Behalten als Ad-hoc-Debug-Werkzeug
  oder weg? (Die *Bibliotheks*-Funktionen beider Dateien sind stark genutzt — nur die
  Einstiegspunkte/Configs stehen zur Debatte.)
- `foundation/execution.py`-`__main__` (Standalone-MC-Report) — Bibliothek bleibt sicher,
  der Einstiegspunkt ist fraglich.

### C. Struktur-Smell (kein toter Code, aber Aufräum-Kandidat)

- `portfolio/equity_report.py` hat eine Doppelrolle: Standalone-Report UND
  Statistik-Bibliothek. `edge_stats`, `risk_stats`, `daily_equity` sowie die **privaten**
  Namen `_market_trades`, `_REPO_ROOT`, `_START_BALANCE` werden von factsheet, verdict,
  regime, correlation, swap_analysis und monitoring importiert — private Namen quer durchs
  Repo. → Statistik in ein eigenes Modul (z.B. `portfolio/stats.py`) ziehen.
- `backtest/pipeline.py` enthält nur noch `make_extract_fn` — einsortieren (z.B. zu
  `portfolio/trades.py` oder in die Stage), Datei auflösen.
- `swap_analysis.py` refresht den Snapshot standardmäßig für MEX_ATLANTIC — sollte
  `standard_broker()`/TTP sein (Teil der bekannten MEX-Altlast).

### D. Docs-Museum

- `docs/mt5-bridge-plan.md` — der Plan ist vollständig umgesetzt (Bridge läuft live).
  Löschen; die Git-Historie bewahrt ihn.
- `docs/roadmap.md` — `[STATUS]`-Marker gegen die Realität prüfen (TTP ist live,
  Zwei-Konten-Architektur steht); vermutlich stark veraltet.
