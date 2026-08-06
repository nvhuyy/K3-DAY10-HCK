# Corruption, Repair & Comparison Report

## Three-state comparison

| Metric / signal | Baseline | Corrupted | Repaired |
|---|---:|---:|---:|
| Retrieval hit rate | 1.000 | 0.500 | 1.000 |
| Mean token F1 | 0.067 | 0.046 | 0.067 |
| Judge accuracy | 0.000 | 0.000 | 0.000 |
| Mean judge score | 1.000 | 1.000 | 1.000 |
| Quality status | PASS | FAIL | PASS |
| Duplicate paper IDs | 0 | 1 | 0 |
| Stale rows | 0 | 1 | 0 |
| Freshness | PASS | FAIL | PASS |

## Findings

Removing frozen-test documents has the strongest retrieval impact because the relevant evidence is absent from the index; noise and blank summaries further weaken semantic matching and answer content.

Repair is rebuilt from the saved raw C2 snapshot so all three states use the same immutable source population. Fetching the API again could return changed records or dates, introducing dataset drift and making the comparison non-reproducible.
