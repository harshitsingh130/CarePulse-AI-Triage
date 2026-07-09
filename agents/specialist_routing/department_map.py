"""Department mapping configuration and matching logic.

Rule-based symptom-to-department matching with keyword analysis.
Falls back to LLM reasoning for ambiguous cases.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DepartmentConfig:
    """Configuration for a specialist department."""

    name: str
    primary_keywords: list[str] = field(default_factory=list)
    associated_keywords: list[str] = field(default_factory=list)
    exclusion_keywords: list[str] = field(default_factory=list)
    default_confidence: float = 0.85


# 10 departments for MVP
DEPARTMENTS: list[DepartmentConfig] = [
    DepartmentConfig(
        name="Cardiology",
        primary_keywords=["chest pain", "heart", "palpitations", "palpitation", "blood pressure", "hypertension", "cardiac"],
        associated_keywords=["shortness of breath", "sweating", "arm pain", "jaw pain", "dizzy"],
        exclusion_keywords=["cough", "fever", "wheezing"],
        default_confidence=0.85,
    ),
    DepartmentConfig(
        name="Neurology",
        primary_keywords=["headache", "migraine", "dizziness", "numbness", "tingling", "seizure", "vision changes", "vertigo"],
        associated_keywords=["confusion", "weakness", "speech difficulty", "light sensitivity"],
        exclusion_keywords=["ear pain", "sinus", "congestion"],
        default_confidence=0.85,
    ),
    DepartmentConfig(
        name="Orthopedics",
        primary_keywords=["joint pain", "back pain", "knee", "shoulder", "fracture", "sprain", "bone", "muscle pain", "hip pain", "ankle"],
        associated_keywords=["swelling", "limited movement", "injury", "fall", "stiffness"],
        exclusion_keywords=["rash", "fever", "internal"],
        default_confidence=0.90,
    ),
    DepartmentConfig(
        name="Gastroenterology",
        primary_keywords=["stomach pain", "abdominal pain", "nausea", "vomiting", "diarrhea", "reflux", "bloating", "heartburn", "constipation"],
        associated_keywords=["blood in stool", "weight loss", "appetite loss", "cramping"],
        exclusion_keywords=["urinary", "kidney", "bladder"],
        default_confidence=0.85,
    ),
    DepartmentConfig(
        name="Pulmonology",
        primary_keywords=["cough", "shortness of breath", "wheezing", "asthma", "breathing difficulty", "chest tightness"],
        associated_keywords=["sputum", "fever", "night sweats", "oxygen"],
        exclusion_keywords=["chest pain without cough", "palpitations"],
        default_confidence=0.85,
    ),
    DepartmentConfig(
        name="Dermatology",
        primary_keywords=["rash", "skin", "itching", "acne", "mole", "lesion", "eczema", "psoriasis", "hives"],
        associated_keywords=["spreading", "color change", "bleeding mole", "flaking"],
        exclusion_keywords=[],
        default_confidence=0.90,
    ),
    DepartmentConfig(
        name="ENT",
        primary_keywords=["ear pain", "sore throat", "sinus", "hearing loss", "nasal", "tinnitus", "hoarse", "congestion"],
        associated_keywords=["post-nasal drip", "ear pressure", "runny nose"],
        exclusion_keywords=["headache without ear", "vision"],
        default_confidence=0.85,
    ),
    DepartmentConfig(
        name="Urology",
        primary_keywords=["urinary", "bladder", "kidney pain", "blood in urine", "frequent urination", "prostate"],
        associated_keywords=["burning sensation", "lower back pain", "groin pain", "difficulty urinating"],
        exclusion_keywords=["abdominal bloating", "stomach"],
        default_confidence=0.85,
    ),
    DepartmentConfig(
        name="Psychiatry",
        primary_keywords=["anxiety", "depression", "depressed", "insomnia", "mood", "panic", "stress", "mental health", "sleep problems"],
        associated_keywords=["sleep changes", "appetite changes", "concentration", "self-harm", "hopelessness"],
        exclusion_keywords=[],
        default_confidence=0.80,
    ),
    DepartmentConfig(
        name="Internal Medicine",
        primary_keywords=["fatigue", "fever", "weight loss", "general", "multiple symptoms", "weakness", "malaise"],
        associated_keywords=["any"],
        exclusion_keywords=[],
        default_confidence=0.60,  # Catch-all — lowest confidence
    ),
]


@dataclass
class MatchResult:
    """Result of department matching."""

    department: str
    confidence: float
    method: str  # "rule_based" or "ambiguous"
    reasoning: str
    alternatives: list[str] = field(default_factory=list)


def match_department(
    primary_complaint_text: str,
    complaint_category: str,
    associated_symptoms: list[str],
) -> MatchResult:
    """Match patient symptoms to the best specialist department.

    Uses keyword matching against the department configuration.
    Returns the best match or signals ambiguity for LLM fallback.

    Args:
        primary_complaint_text: Patient's primary complaint text.
        complaint_category: Categorized complaint (from symptom assessment).
        associated_symptoms: List of associated symptom strings.

    Returns:
        MatchResult with department, confidence, and alternatives.
    """
    complaint_lower = primary_complaint_text.lower()
    assoc_lower = " ".join(associated_symptoms).lower()
    combined_text = complaint_lower + " " + assoc_lower

    scores: list[tuple[str, float, str]] = []  # (dept_name, score, reasoning)

    for dept in DEPARTMENTS:
        score = 0.0
        reasons: list[str] = []

        # Primary keyword match
        primary_matches = [kw for kw in dept.primary_keywords if kw in complaint_lower]
        if primary_matches:
            score += 0.6
            reasons.append(f"Primary keyword match: {', '.join(primary_matches[:3])}")

        # Associated keyword match (boosts confidence)
        assoc_matches = [kw for kw in dept.associated_keywords if kw in combined_text]
        if assoc_matches and assoc_matches != ["any"]:
            score += 0.25
            reasons.append(f"Associated symptom match: {', '.join(assoc_matches[:3])}")

        # Exclusion keyword check (disqualifies)
        exclusion_matches = [kw for kw in dept.exclusion_keywords if kw in combined_text]
        if exclusion_matches:
            score -= 0.5
            reasons.append(f"Exclusion keyword: {', '.join(exclusion_matches)}")

        if score > 0:
            reasoning = "; ".join(reasons)
            scores.append((dept.name, score, reasoning))

    # Sort by score descending
    scores.sort(key=lambda x: x[1], reverse=True)

    if not scores:
        # No matches at all — route to Internal Medicine
        return MatchResult(
            department="Internal Medicine",
            confidence=0.50,
            method="rule_based",
            reasoning="No department keywords matched. Routing to Internal Medicine as catch-all.",
            alternatives=[],
        )

    best = scores[0]
    best_name, best_score, best_reasoning = best

    # Check for ambiguity (two departments with similar scores)
    if len(scores) >= 2:
        second_name, second_score, _ = scores[1]
        if best_score - second_score < 0.15:
            # Ambiguous — close scores
            return MatchResult(
                department=best_name,
                confidence=0.55,  # Low confidence signals need for LLM
                method="ambiguous",
                reasoning=f"Ambiguous match between {best_name} and {second_name}. {best_reasoning}",
                alternatives=[second_name],
            )

    # Clear winner
    confidence = min(0.95, best_score + 0.3)  # Boost from base score
    return MatchResult(
        department=best_name,
        confidence=confidence,
        method="rule_based",
        reasoning=best_reasoning,
        alternatives=[s[0] for s in scores[1:3]],  # Top 2 alternatives
    )


# Clinic network configuration for MVP
CLINIC_NETWORK: dict[str, dict] = {
    "clinic-01": {
        "name": "Healthcare Network - Main Campus",
        "departments": ["Cardiology", "Neurology", "Orthopedics", "Gastroenterology", "Pulmonology",
                       "Dermatology", "ENT", "Urology", "Psychiatry", "Internal Medicine"],
        "alternatives": ["clinic-02", "clinic-03"],
    },
    "clinic-02": {
        "name": "Healthcare Network - Westside",
        "departments": ["Orthopedics", "Gastroenterology", "Dermatology", "ENT", "Internal Medicine"],
        "alternatives": ["clinic-01", "clinic-03"],
    },
    "clinic-03": {
        "name": "Healthcare Network - Eastside",
        "departments": ["Cardiology", "Pulmonology", "Neurology", "Psychiatry", "Internal Medicine"],
        "alternatives": ["clinic-01", "clinic-02"],
    },
    "clinic-04": {
        "name": "Healthcare Network - North",
        "departments": ["Orthopedics", "ENT", "Urology", "Internal Medicine"],
        "alternatives": ["clinic-01", "clinic-02"],
    },
    "clinic-05": {
        "name": "Healthcare Network - South",
        "departments": ["Gastroenterology", "Dermatology", "Psychiatry", "Internal Medicine"],
        "alternatives": ["clinic-01", "clinic-03"],
    },
}
