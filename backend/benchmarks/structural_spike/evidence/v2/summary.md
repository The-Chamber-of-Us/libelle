# Benchmark Summary

**Timestamp:** 2026-09-30 15:13:51  
**Git Commit:** `e04ab03`  
**Parsers:** libelle

## Scoreboard

| Parser | Field | Micro-F1 | Macro-F1 | Std Dev |
|--------|-------|----------|----------|---------|
| libelle | location | 0.824 | 0.700 | 0.458 |
| libelle | skills | 0.644 | 0.602 | 0.374 |
| libelle | skills_resolved | 0.644 | 0.602 | 0.374 |

## Resolver Coverage on Parser Output

- Average resolver coverage on parser output: `0.112`
- Resolver rows counted: `8`
- Unknown skills captured: `89`
- Note: This measures resolver alias-map coverage over skills emitted by the parser. It is not end-to-end parser skill recovery against the gold skills; TP / FP / FN / precision / recall / F1 scoring above remains unchanged.

## Top False-Positive Cases

| Resume | Field | Parser | FP Count |
|--------|-------|--------|----------|
| resume_204 | skills | libelle | 22 |
| resume_204 | skills_resolved | libelle | 22 |
| resume_207 | skills | libelle | 16 |

## Top False-Negative Cases

| Resume | Field | Parser | TP Count | FN Count |
|--------|-------|--------|----------|----------|
| resume_206 | skills | libelle | 0 | 10 |
| resume_206 | skills_resolved | libelle | 0 | 10 |
| resume_202 | skills | libelle | 11 | 8 |

## Zero-TP Cases (Severe Recall Loss)

| Resume | Field | Parser | FN Count |
|--------|-------|--------|----------|
| resume_206 | skills | libelle | 10 |
| resume_206 | skills_resolved | libelle | 10 |
| resume_209 | skills | libelle | 5 |