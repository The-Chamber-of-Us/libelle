# Benchmark Failure Examples

## False Positives (predicted but not in golden)

**Resume:** `dense_skills_01` | **Parser:** `libelle` | **Field:** `skills`
- FP examples: account creation by 35%., adobe, and retail, and user research synthesis. conducted moderated usability, apps across ios and android

**Resume:** `dense_skills_01` | **Parser:** `libelle` | **Field:** `skills_resolved`
- FP examples: accountcreationby35, adobe, andretail, anduserresearchsynthesis.conductedmoderatedusability, appsacrossiosandandroid

**Resume:** `header_contact_01` | **Parser:** `libelle` | **Field:** `skills`
- FP examples: calendar), communication, compliance, confidentiality & ferpa, cpr certified

**Resume:** `header_contact_01` | **Parser:** `libelle` | **Field:** `skills_resolved`
- FP examples: communication, compliance, confidentialityferpa, cprcertified, dataentrydatabase

**Resume:** `multi_col_02` | **Parser:** `libelle` | **Field:** `skills`
- FP examples: compound and stereo, documentation, environmental testing, instruments, laboratory information


## False Negatives (in golden but not predicted)

**Resume:** `dense_skills_02` | **Parser:** `libelle` | **Field:** `skills`
- FN examples: ad copy, blog writing, brand voice development, case studies, content strategy

**Resume:** `dense_skills_02` | **Parser:** `libelle` | **Field:** `skills_resolved`
- FN examples: adcopy, blogwriting, brandvoicedevelopment, casestudies, contentstrategy

**Resume:** `header_contact_01` | **Parser:** `libelle` | **Field:** `skills`
- FN examples: calendar, confidentiality & ferpa compliance, data entry & database management, docs, english

**Resume:** `header_contact_01` | **Parser:** `libelle` | **Field:** `skills_resolved`
- FN examples: confidentialityferpacompliance, dataentrydatabasemanagement, docs, english, firstaid/cprcertified

**Resume:** `dense_skills_01` | **Parser:** `libelle` | **Field:** `skills`
- FN examples: adobe photoshop, agile/scrum, axure rp, heuristic evaluation, information architecture
