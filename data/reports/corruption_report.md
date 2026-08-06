# Corruption Comparison Report

## RAG Evaluation Comparison
| Metric | Baseline | Corrupted | Repaired | Corrupted Δ | Repaired Δ | Recovery |
|---|---:|---:|---:|---:|---:|---:|
| retrieval_hit_rate | 1.000 | 0.750 | 1.000 | -0.250 | +0.000 | 100.00% |
| mean_token_f1 | 0.067 | 0.065 | 0.068 | -0.002 | +0.002 | 200.01% |
| judge_accuracy | 0.000 | 0.000 | 0.000 | +0.000 | +0.000 | N/A |
| mean_judge_score | 1.000 | 1.000 | 1.000 | +0.000 | +0.000 | N/A |

## Data Quality Comparison
### Row count
- Corrupted: 24
- Repaired: 24

### Freshness Status
- Corrupted: needs attention (Stale rows: 3)
- Repaired: fresh (Stale rows: 0)

## Detailed Quality Notes
**Corrupted Quality:**
```json
{'report_name': 'corrupted_quality.json', 'row_count': 24, 'completeness': {'paper_id': 1.0, 'title': 1.0, 'summary': 0.8333}, 'uniqueness': {'paper_id_unique': False, 'duplicate_paper_ids': 2}, 'freshness': {'stale_rows': 3, 'freshness_threshold_days': 180, 'max_age_days': 3744, 'is_fresh': False}}
```

**Repaired Quality:**
```json
{'report_name': 'repaired_quality.json', 'row_count': 24, 'completeness': {'paper_id': 1.0, 'title': 1.0, 'summary': 1.0}, 'uniqueness': {'paper_id_unique': True, 'duplicate_paper_ids': 0}, 'freshness': {'stale_rows': 0, 'freshness_threshold_days': 180, 'max_age_days': 161, 'is_fresh': True}}
```
