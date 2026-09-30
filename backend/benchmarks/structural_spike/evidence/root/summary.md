# Benchmark Summary

**Timestamp:** 2026-09-30 15:13:47  
**Git Commit:** `e04ab03`  
**Parsers:** libelle

## Scoreboard

| Parser | Field | Micro-F1 | Macro-F1 | Std Dev |
|--------|-------|----------|----------|---------|
| libelle | location | 0.733 | 0.550 | 0.497 |
| libelle | skills | 0.655 | 0.720 | 0.266 |
| libelle | skills_resolved | 0.670 | 0.731 | 0.261 |

## Resolver Coverage on Parser Output

- Average resolver coverage on parser output: `0.019`
- Resolver rows counted: `19`
- Unknown skills captured: `315`
- Note: This measures resolver alias-map coverage over skills emitted by the parser. It is not end-to-end parser skill recovery against the gold skills; TP / FP / FN / precision / recall / F1 scoring above remains unchanged.

## Top False-Positive Cases

| Resume | Field | Parser | FP Count |
|--------|-------|--------|----------|
| dense_skills_01 | skills | libelle | 46 |
| dense_skills_01 | skills_resolved | libelle | 46 |
| header_contact_01 | skills | libelle | 16 |

## Top False-Negative Cases

| Resume | Field | Parser | TP Count | FN Count |
|--------|-------|--------|----------|----------|
| dense_skills_02 | skills | libelle | 0 | 22 |
| dense_skills_02 | skills_resolved | libelle | 0 | 22 |
| header_contact_01 | skills | libelle | 14 | 16 |

## Zero-TP Cases (Severe Recall Loss)

| Resume | Field | Parser | FN Count |
|--------|-------|--------|----------|
| dense_skills_02 | skills | libelle | 22 |
| dense_skills_02 | skills_resolved | libelle | 22 |
| embed_link_02 | location | libelle | 1 |