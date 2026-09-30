# Benchmark Failure Examples

## False Positives (predicted but not in golden)

**Resume:** `resume_204` | **Parser:** `libelle` | **Field:** `skills`
- FP examples: - built r markdown templates for analysis notes so collaborators could review assumptions, - completed coursework in causal inference, - coordinate speaker questions for visiting researchers presenting climate and health work., - summarize methods limitations and data-source constraints for monthly article discussions., 2025-2026

**Resume:** `resume_204` | **Parser:** `libelle` | **Field:** `skills_resolved`
- FP examples: 2025-2026, andmodelchanges, andreproducibleresearch, builtrmarkdowntemplatesforanalysisnotessocollaboratorscouldreviewassumptions, completedcourseworkincausalinference

**Resume:** `resume_207` | **Parser:** `libelle` | **Field:** `skills`
- FP examples: - added concise case-study summaries so project links were meaningful outside the visual portfolio context., - audited project pages for heading order, - converted research findings into user stories and acceptance criteria for a partner engineering backlog., - interviewed business owners about permit terminology, 2026

**Resume:** `resume_207` | **Parser:** `libelle` | **Field:** `skills_resolved`
- FP examples: 2026, addedconcisecase-studysummariessoprojectlinksweremeaningfuloutsidethevisualportfoliocontext, anddescriptivelinktext, andstatus-notificationgaps, auditedprojectpagesforheadingorder

**Resume:** `resume_208` | **Parser:** `libelle` | **Field:** `skills`
- FP examples: dashboard, qa, sql basics


## False Negatives (in golden but not predicted)

**Resume:** `resume_206` | **Parser:** `libelle` | **Field:** `skills`
- FN examples: arcgis pro, autocad civil 3d, english, excel, french

**Resume:** `resume_206` | **Parser:** `libelle` | **Field:** `skills_resolved`
- FN examples: arcgispro, autocadcivil3d, english, excel, french

**Resume:** `resume_202` | **Parser:** `libelle` | **Field:** `skills`
- FN examples: aws, bash, django, gcp, go

**Resume:** `resume_202` | **Parser:** `libelle` | **Field:** `skills_resolved`
- FN examples: aws, bash, django, gcp, go

**Resume:** `resume_209` | **Parser:** `libelle` | **Field:** `skills`
- FN examples: arabic, excel, java, python, sql
