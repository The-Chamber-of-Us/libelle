import re
import us
from typing import List, Dict, Tuple, Any
from utils.text_normalization import normalize_text


def _get_lines(text: str) -> List[str]:
    return [line.rstrip() for line in text.splitlines()]

def _clean_line(line: str) -> str:
    return re.sub(r'[\s_\-=*]+$', '', line.strip())

def _is_section_header(line: str) -> bool:
    if not line or len(line.strip()) == 0:
        return False
    
    # exclude single uppercase skills like 'SQL' on its own line
    if line.strip().startswith(('•','-', '—', '*')): # generally used for indidividual skills
        return False
    
    s = _clean_line(line)

    # fixing garbled spacing e.g. "Sk i ll s" to "Skills"
    tokens = s.split()
    if len(tokens) >= 3 and sum(len(t) for t in tokens) / len(tokens) <= 2.5:
        s = s.replace(' ', '')

    headers = [
        r'^(summary|objective|contact|education|certifi|certificate|skills|'
        r'tools|tech\s+stack|toolkit|technical\s+toolkit|core\s+technologies|technical\s+expertise|'
        r'work experience|professional experience|experience|employment|'
        r'job experience|'
        r'career history|work history|relevant experience|'
        r'projects|project experience|project|research|publications|'
        r'awards|volunteer|volunteering|volunteer experience|honors|activities|'
        r'additional information|references|languages|interests|certifications):?$'
    ]

    if re.match(headers[0], s.lower()):
        return True
    return False

def _collect_section_lines(lines: List[str], start_patterns: List[str], stop_when_header: bool = True):
    start_re = re.compile('|'.join(start_patterns), re.IGNORECASE)
    collected = []
    capturing = False
    end_index = len(lines)
    for i, line in enumerate(lines):
        cleaned = _clean_line(line)
        # for garbled spacing
        tokens = cleaned.split()
        if len(tokens) >= 3 and sum(len(t) for t in tokens) / len(tokens) <= 2.5:
            cleaned = cleaned.replace(' ', '')
        
        if not capturing and start_re.match(cleaned):
            capturing = True
            continue
        if capturing:
            if stop_when_header and _is_section_header(line):
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

def extract_phone(text: str) -> Tuple[List[str], float]:
    pattern = r"(\+?\d[\d\s().-]{8,}\d)"
    raw_matches = re.findall(pattern, text)
    cleaned = [re.sub(r"[^\d]", "", n) for n in raw_matches if 9 <= len(re.sub(r"[^\d]", "", n)) <= 15]
    confidence = 1.0 if cleaned else min(1.0, sum(1 for _ in re.findall(r"\d{5,}", text)) / 2)
    return cleaned, confidence

def _strip_contact_tokens(line: str) -> str:
    """Remove email, phone, and URL fragments from a line, leaving other text intact."""
    # emails
    line = re.sub(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', '', line)
    # URLs (before phone, so e.g. tel: links don't confuse phone pattern)
    line = re.sub(r'https?://\S+', '', line)
    line = re.sub(r'(?:www\.|github\.com|linkedin\.com)\S*', '', line, flags=re.IGNORECASE)
    # phones - properly escaped this time
    line = re.sub(r'\+?\d[\d\s().\-]{7,}\d', '', line)
    # clean up leftover delimiters and whitespace
    line = re.sub(r'[\|•·]+', ' ', line)
    return line.strip()


def extract_location(text: str) -> Tuple[List[str], float]:
    job_keywords = ["Engineer", "Developer", "Manager", "Intern", "Inc.", "LLC"]
    state_codes = set(s.abbr for s in us.states.STATES_AND_TERRITORIES)

    lines = [l.strip() for l in text.splitlines() if l.strip()]

    for line in lines[:15]:
        # Work with contact tokens stripped out without discarding the line
        scrubbed = _strip_contact_tokens(line)
        if not scrubbed:
            continue

        if re.search(r'\b(remote|hybrid)\b', scrubbed, re.IGNORECASE):
            return [scrubbed.strip()], 1.0

        parts = scrubbed.split(",")
        if len(parts) >= 2:
            tokens = parts[1].strip().upper().split()
            if tokens:
                state_candidate = tokens[0]
                if state_candidate in state_codes:
                    return [scrubbed.strip()], 1.0

        if any(re.search(rf'\b({job})\b', scrubbed, re.IGNORECASE) for job in job_keywords):
            continue

    return [], 0.0

def _split_skill_line(line: str) -> List[str]:
    if '/' in line and '://' not in line:
        parts = [p.strip() for p in line.split('/')]
        if (all(p and len(p) < 40 and not p.isdigit() for p in parts)
                and not any(re.search(r'\b[A-Z]{1,3}$', p) for p in parts)
                and not any(re.match(r'^[A-Z]{1,3}$', p) for p in parts)):  # catches CI, CD, AB etc
            return parts
    return re.split(r'[•,·;|]', line)

def _clean_skill_fragment(fragment: str) -> str:
    return re.sub(r'^[\s•·\-\—*]+|[\s•·\-\—*]+$', '', fragment)

def extract_skills(text: str) -> Tuple[List[str], float]:
    skills_patterns = [
        r'^skills:?$',
        r'^technical\s+skills:?$',
        r'^tools:?$',
        r'^tech\s+stack:?$',
        r'^toolkit:?$',
        r'^technical\s+toolkit:?$',
        r'^core\s+technologies:?$',
        r'^core\s+skills:?$',
        r'^key\s+skills:?$',
        r'^professional\s+skills:?$',
        r'^technical\s+proficiencies:?$',
        r'^core\s+competencies:?$',
        r'^competencies:?$',
        r'^technologies:?$',
        r'^tools\s+(?:&|and)\s+technologies:?$',
        r'^areas\s+of\s+expertise:?$',
        r'^skills\s+(?:&|and)\s+expertise:?$',
        r'^technical\s+expertise:?$',
        r'^programming\s+languages:?$',
        r'^qualifications:?$',
    ]

    lines = _get_lines(text)
    skills_lines, _ = _collect_section_lines(lines, skills_patterns)
    cleaned = []
    for l in skills_lines:
        if re.match(r'^[^:]{1,40}:\s+\S', l):
            l = re.sub(r'^[^:]+:\s*', '', l)
        l = re.sub(r'\s*\(.*?\)', '', l) # strips parentheses
        cleaned.append(l)

    skills = [
        normalize_text(skill, lowercase=True)
        for l in cleaned
        for p in _split_skill_line(l)
        for skill in [_clean_skill_fragment(p)]
        if skill
    ]
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
    
    work_patterns = [
        r'^(work|professional)\s+experience:?$',
        r'^experience:?$',
        r'^employment:?$',
        r'^career\s+history:?$',
        r'^work\s+history:?$',
        r'^relevant\s+experience:?$',
        r'^job\s+experience:?$',
    ]

    work_lines, work_end = _collect_section_lines(lines, work_patterns)
    entries = _group_into_entries(work_lines)
    conf = 1.0 if entries else min(1.0, len(work_lines) / max(1, len(lines)))
    return entries, conf, work_end

def extract_project_experience(text: str, start_index: int) -> Tuple[List[str], float]:
    lines = _get_lines(text)[start_index:]

    project_patterns = [
        r'^project\s+experience:?$',
        r'^projects:?$'
    ]

    project_lines, _ = _collect_section_lines(lines, project_patterns)
    entries = _group_into_entries(project_lines)
    conf = 1.0 if entries else min(1.0, len(project_lines) / max(1, len(lines)))
    return entries, conf

def parse_resume(text: str) -> Dict[str, Any]:
    phones, phone_conf = extract_phone(text)
    locations, loc_conf = extract_location(text)
    skills, skills_conf = extract_skills(text)
    education, edu_conf = extract_education(text)
    work_experience, work_conf, work_end_index = extract_work_experience(text)
    project_experience, project_conf = extract_project_experience(text, work_end_index)
    return {
        "name": {"value": "", "confidence": 0.0},
        "emails": {"value": "", "confidence": 0.0},
        "phones": {"value": phones, "confidence": phone_conf},
        "locations": {"value": locations, "confidence": loc_conf},
        "skills": {"value": skills, "confidence": skills_conf},
        "education": {"value": education, "confidence": edu_conf},
        "work_experience": {"value": work_experience, "confidence": work_conf},
        "project_experience": {"value": project_experience, "confidence": project_conf},
    }
