import re
from typing import Tuple, List, Optional

KNOWN_JOCKEYS = frozenset({
    "fourie", "murray", "veale", "habib", "zackey", "lerena",
    "de melo", "lloyd", "moodley", "khumalo", "yeni", "marcus",
    "domeyer", "schofield", "little", "godden",
})

KNOWN_TRAINERS = frozenset({
    "snaith", "tarry", "kock", "peter", "laird", "azzie", "klaasen",
    "woodruff", "kotzen", "crawford", "kannemeyer", "marshall", "bass",
    "puller", "steyn", "wright", "dawson", "bronkhorst", "ferrie", "rivalland",
})

_FORM_CLEAN_NUM_RE = re.compile(r'^#\d+|\b\d+\.?\d*kg\b|\b\d+yo\b')
_FORM_PAREN_RE = re.compile(r'\(([^)]+)\)')
_FORM_DASH_SEQ_RE = re.compile(r'\b([0-9\-]+-[0-9\-]+)\b')
_FORM_GENERIC_RE = re.compile(r'\b([0-9\-]{3,})\b')
_FORM_KEYWORD_RE = re.compile(r'(?i)(?:form\s+)?\b([0-9\-]{3,})\b')

_JT_COMMA_RE = re.compile(r'(?i)trainer\s+([A-Za-z\s]+?),\s*jockey\s+([A-Za-z\s]+)')
_JT_SLASH_RE = re.compile(r'([A-Za-z\s\.\-]+?)/([A-Za-z\s\.\-]+)')
_JT_WORD_RE = re.compile(r'[A-Za-z]+')


def extract_form_string(text: str) -> str:
    cleaned_text = _FORM_CLEAN_NUM_RE.sub('', text)

    paren_matches = _FORM_PAREN_RE.findall(cleaned_text)
    for match in paren_matches:
        if 'kg' in match.lower() or 'yo' in match.lower() or 'year' in match.lower():
            continue
        clean = re.sub(r'[^0-9\-]', '', match)
        if len(clean) >= 2 and '-' in clean:
            return clean
        if len(clean) >= 3:
            return clean

    form_match = _FORM_KEYWORD_RE.search(cleaned_text)
    if form_match:
        return re.sub(r'[^0-9\-]', '', form_match.group(1))

    dash_match = _FORM_DASH_SEQ_RE.search(cleaned_text)
    if dash_match:
        return re.sub(r'[^0-9\-]', '', dash_match.group(1))

    for g in _FORM_GENERIC_RE.findall(cleaned_text):
        clean = re.sub(r'[^0-9\-]', '', g)
        if '-' in clean or len(clean) >= 3:
            return clean
    return ""


def detect_jockey_trainer(text: str) -> Tuple[str, str]:
    match1 = _JT_COMMA_RE.search(text)
    if match1:
        return match1.group(2).strip(), match1.group(1).strip()

    match2 = _JT_SLASH_RE.search(text)
    if match2:
        return match2.group(2).strip(), match2.group(1).strip()

    words = _JT_WORD_RE.findall(text)
    jockey = ""
    trainer = ""
    for w in words:
        w_lower = w.lower()
        if w_lower in KNOWN_JOCKEYS and not jockey:
            jockey = w
        if w_lower in KNOWN_TRAINERS and not trainer:
            trainer = w

    return jockey, trainer


def get_jockey_trainer_multiplier(jockey: str, trainer: str) -> float:
    mult = 1.0
    if jockey.lower() in KNOWN_JOCKEYS:
        mult += 0.05
    if trainer.lower() in KNOWN_TRAINERS:
        mult += 0.05
    return mult


def compute_win_probability(form_str: str, weight: float, jockey: str, trainer: str, field_size: int) -> float:
    from core_agent.skills.race_analysis.form_analyzer import FormAnalyzer, parse_sa_form

    positions = parse_sa_form(form_str)
    analyzer = FormAnalyzer()

    base_prob, _, _ = analyzer.estimate_win_probability(
        horse_name="candidate",
        form_positions=positions,
        field_size=field_size,
    )

    weight_diff = weight - 58.0
    weight_factor = 1.0 - (weight_diff * 0.008)
    weight_factor = max(0.8, min(1.2, weight_factor))

    jt_mult = get_jockey_trainer_multiplier(jockey, trainer)

    final_prob = base_prob * weight_factor * jt_mult
    return max(0.01, min(0.75, final_prob))
