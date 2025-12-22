from nameparser import HumanName
from names_dataset import NameDataset
import re
import us
from typing import List, Dict, Tuple, Any

nd = NameDataset()

def _get_lines(text: str) -> List[str]:
    return [line.rstrip() for line in text.splitlines()]

def _is_section_header(line: str) -> bool:
    if not line or len(line.strip()) == 0:
        return False
    s = line.strip()
    headers = [
        r'^(summary|objective|contact|education|certifi|certificate|skills|work experience|work|experience|employment|projects|project experience|project|research|publications|awards|volunteer|honors|activities)$'
    ]
    if re.match(headers[0], s.lower()):
        return True
    if s == s.upper() and len(s) < 60 and ' ' in s:
        return True
    return False

def _collect_section_lines(lines: List[str], start_patterns: List[str], stop_when_header: bool = True):
    start_re = re.compile(r'|'.join([f'({p})' for p in start_patterns]), re.IGNORECASE)
    collected = []
    capturing = False
    end_index = len(lines)
    for i, line in enumerate(lines):
        if not capturing and start_re.search(line or ""):
            capturing = True
            continue
        if capturing:
            if stop_when_header and _is_section_header(line.strip()):
                end_index = i
                break
            collected.append(line)
    return collected, end_index

def _group_into_entries(section_lines: List[str]) -> List[str]:
    entries, current = [], []
    def flush_current():
        if current:
            text = " ".join([ln.strip() for ln in current if ln.strip()])
            text = re.sub(r'\s+', ' ', text).strip()
            if text:
                entries.append(text)
            current.clear()
    date_like = re.compile(
        r'\b(?:\d{4}|\d{4}\s*-\s*\d{4}|Present|present|Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|'
        r'Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|'
        r'Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)', re.IGNORECASE)
    for line in section_lines:
        stripped = line.strip()
        if not stripped:
            flush_current()
            continue
        if stripped.startswith(('•', '-', '—')):
            flush_current()
            current.append(re.sub(r'^[•\-\—]\s*', '', stripped))
            continue
        if (date_like.search(stripped) and len(current) > 0) and len(current[-1].strip()) > 0:
            current.append(stripped)
            continue
        if re.search(r'\|', stripped) and date_like.search(stripped):
            flush_current()
            current.append(stripped)
            continue
        if re.match(r'^[A-Z][\w&\.\-]+', stripped) and date_like.search(stripped) and not current:
            current.append(stripped)
            continue
        current.append(stripped)
    flush_current()
    return entries

def extract_email(text: str) -> Tuple[List[str], float]:
    matches = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
    confidence = 1.0 if matches else min(1.0, sum(1 for w in text.split() if "@" in w) / 2)
    return matches, confidence

def extract_phone(text: str) -> Tuple[List[str], float]:
    pattern = r"(\+?\d[\d\s().-]{8,}\d)"
    raw_matches = re.findall(pattern, text)
    cleaned = [re.sub(r"[^\d]", "", n) for n in raw_matches if 9 <= len(re.sub(r"[^\d]", "", n)) <= 15]
    confidence = 1.0 if cleaned else min(1.0, sum(1 for _ in re.findall(r"\d{5,}", text)) / 2)
    return cleaned, confidence

def extract_name(text: str) -> Tuple[str, float]:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    stop_headers = ["education", "work", "experience", "employment", "projects", "skills", "summary", "objective", "volunteer", "leadership"]
    for line in lines:
        if any(h in line.lower() for h in stop_headers):
            break
        line_no_email = re.sub(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "", line).strip()
        line_no_contact = re.sub(r"\+?\d[\d\s().-]{8,}\d", "", line_no_email).strip()
        if not line_no_contact:
            continue
        candidate = HumanName(line_no_contact)
        score = 0.0
        if candidate.first and nd.first_names.get(candidate.first.lower()):
            score += 0.5
        if candidate.last and nd.last_names.get(candidate.last.lower()):
            score += 0.5
        if score > 0:
            return str(candidate).strip(), min(score, 1.0)
    return "Name Not Found", 0.0

def extract_location(text: str) -> Tuple[List[str], float]:
    job_keywords = ["Engineer", "Developer", "Manager", "Intern", "Inc.", "LLC"]   ## Potential Job Titles  
    state_codes = set(s.abbr for s in us.states.STATES_AND_TERRITORIES)            ## All 50 States + Abbreviations

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    candidate_lines = [l for l in lines[:15] if not re.search(r"[a-zA-Z0-9._%+-]+@|\\+?\\d[\\d\\s().-]{8,}\\d|https?://\S+", l)]   ##Filtering out email, phone numbers, or URLs
    for line in candidate_lines:
        if re.search(r'\b(remote|hybrid)\b', line, re.IGNORECASE):
            return [line.strip()], 1.0
    
        parts = line.split(",")
        if (len(parts) >= 2):
            state_candidate = parts[1].strip().upper().split()[0]
            if (state_candidate in state_codes):
                return [line.strip()], 1.0
        if any(re.search(rf'\b({job})\b', line, re.IGNORECASE) for job in job_keywords):
                continue
    return [], 0.0

def extract_skills(text: str) -> Tuple[List[str], float]:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    skills_lines, in_skills_section = [], False
    for line in lines:
        if re.search(r'\bskills\b', line, re.IGNORECASE):
            in_skills_section = True
            continue
        elif in_skills_section and re.match(r'^[A-Z][A-Z\s&]+$', line) and len(line) < 50:
            break
        elif in_skills_section:
            skills_lines.append(line)
    skills = [p.strip() for l in skills_lines for p in re.split(r'•|,|·|;', l) if p.strip()]
    confidence = 1.0 if skills else 0.0
    return skills, confidence

def extract_education(text: str) -> Tuple[List[str], float]:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    edu_lines, in_section = [], False
    for line in lines:
        if re.search(r'\beducation\b', line, re.IGNORECASE):
            in_section = True
            continue
        elif in_section and re.match(r'^[A-Z][A-Z\s&]+$', line) and len(line) < 50:
            break
        elif in_section:
            edu_lines.append(line)
    return edu_lines, 1.0 if edu_lines else 0.0

def extract_work_experience(text: str) -> Tuple[List[str], float, int]:
    lines = _get_lines(text)
    work_lines, work_end = _collect_section_lines(lines, [r'work experience', r'experience', r'employment'])
    entries = _group_into_entries(work_lines)
    conf = 1.0 if entries else min(1.0, len(work_lines) / max(1, len(lines)))
    return entries, conf, work_end

def extract_project_experience(text: str, start_index: int) -> Tuple[List[str], float]:
    lines = _get_lines(text)[start_index:]
    project_lines, _ = _collect_section_lines(lines, [r'project experience', r'projects', r'project'])
    entries = _group_into_entries(project_lines)
    conf = 1.0 if entries else min(1.0, len(project_lines) / max(1, len(lines[start_index:])))
    return entries, conf

def parse_resume(text: str) -> Dict[str, Any]:
    name, name_conf = extract_name(text)
    emails, email_conf = extract_email(text)
    phones, phone_conf = extract_phone(text)
    locations, loc_conf = extract_location(text)
    skills, skills_conf = extract_skills(text)
    education, edu_conf = extract_education(text)
    work_experience, work_conf, work_end_index = extract_work_experience(text)
    project_experience, project_conf = extract_project_experience(text, work_end_index)
    return {
        "name": {"value": name, "confidence": name_conf},
        "emails": {"value": emails, "confidence": email_conf},
        "phones": {"value": phones, "confidence": phone_conf},
        "locations": {"value": locations, "confidence": loc_conf},
        "skills": {"value": skills, "confidence": skills_conf},
        "education": {"value": education, "confidence": edu_conf},
        "work_experience": {"value": work_experience, "confidence": work_conf},
        "project_experience": {"value": project_experience, "confidence": project_conf},
    }
