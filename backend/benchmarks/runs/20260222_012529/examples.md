# Benchmark Failure Examples

## False Positives (predicted but not in golden)

**Resume:** `embed_link_01` | **Parser:** `libelle` | **Field:** `skills`
- FP examples: data visualization (matplotlib, powerbi), tableau

**Resume:** `high_signal_01` | **Parser:** `libelle` | **Field:** `skills`
- FP examples: construction planning & qa/qc: construction scheduling, structural engineering: structural load calculations, codes & documentation: design code compliance, design software: autocad, geotechnical & hydrology: soil mechanics fundamentals

**Resume:** `high_signal_01` | **Parser:** `libelle` | **Field:** `location`
- FP examples: predicted country=ca

**Resume:** `high_signal_02` | **Parser:** `libelle` | **Field:** `skills`
- FP examples: linux, cloud & devops: docker, databases: postgresql, environments, programming languages: python

**Resume:** `low_signal_01` | **Parser:** `libelle` | **Field:** `skills`
- FP examples: college of health & nutrition studies, 2020 - 2024, b. sc. dietetics, recent graduate in dietetics with foundational knowledge in nutrition principles and dietary planning. seeking, an entry-level role to gain practical experience in clinical or community nutrition settings.


## False Negatives (in golden but not predicted)

**Resume:** `embed_link_01` | **Parser:** `libelle` | **Field:** `skills`
- FN examples: tableu, data visualization, powerbi, matplotlib

**Resume:** `embed_link_01` | **Parser:** `libelle` | **Field:** `location`
- FN examples: expected country=united states

**Resume:** `embed_link_02` | **Parser:** `libelle` | **Field:** `skills`
- FN examples: conflict management, process improvement, data analytics, team player, budget tracking and cost control

**Resume:** `embed_link_02` | **Parser:** `libelle` | **Field:** `location`
- FN examples: expected country=united states

**Resume:** `high_signal_01` | **Parser:** `libelle` | **Field:** `skills`
- FN examples: autocad, structural load calculations, soil mechanics fundamentals, construction scheduling, design code compliance
