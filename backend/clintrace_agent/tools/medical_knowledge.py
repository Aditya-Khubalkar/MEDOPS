"""Medical knowledge tools for the triage pipeline.

These provide structured reference data that agents can call during reasoning.
"""

from google.adk.tools import FunctionTool


def lookup_esi_criteria(esi_level: int) -> dict:
    """Return the clinical criteria for a given ESI level (1-5).

    Args:
        esi_level: Emergency Severity Index level (1-5).

    Returns:
        Dictionary with criteria, examples, and resource expectations.
    """
    criteria = {
        1: {
            "level": 1,
            "name": "Immediate",
            "description": "Requires immediate life-saving intervention",
            "examples": [
                "Cardiac/respiratory arrest",
                "Major trauma with active hemorrhage",
                "Intubated / apneic / pulseless",
            ],
            "resources": "Full resuscitation team",
            "time_to_provider": "Immediate (0 min)",
        },
        2: {
            "level": 2,
            "name": "Emergent",
            "description": "High risk situation, confused/lethargic, severe pain",
            "vital_thresholds": {
                "hr_high": 150,
                "rr_high": 30,
                "spo2_low": 90,
                "temp_high_f": 104,
                "sbp_low": 80,
            },
            "examples": [
                "Chest pain with cardiac features",
                "Acute stroke symptoms",
                "Overdose with altered mental status",
                "Severe asthma / respiratory distress",
            ],
            "resources": "Multiple (labs, imaging, IV, specialist)",
            "time_to_provider": "< 10 min",
        },
        3: {
            "level": 3,
            "name": "Urgent",
            "description": "Stable but needs multiple resources",
            "examples": [
                "Abdominal pain needing labs + imaging",
                "Fracture needing imaging + reduction",
                "Febrile child needing workup",
            ],
            "resources": "2+ resources expected",
            "time_to_provider": "15-30 min",
        },
        4: {
            "level": 4,
            "name": "Less Urgent",
            "description": "Stable, needs one resource",
            "examples": [
                "Simple laceration needing sutures",
                "Urinary symptoms needing UA",
                "Ankle sprain needing X-ray",
            ],
            "resources": "1 resource expected",
            "time_to_provider": "30-60 min",
        },
        5: {
            "level": 5,
            "name": "Non-Urgent",
            "description": "Stable, no resources needed",
            "examples": [
                "Medication refill",
                "Simple wound check",
                "Minor cold / cough",
            ],
            "resources": "None (exam only)",
            "time_to_provider": "60+ min",
        },
    }
    return criteria.get(esi_level, {"error": f"Invalid ESI level: {esi_level}"})


def lookup_red_flag_criteria(condition: str) -> dict:
    """Return screening criteria for a specific red-flag condition.

    Args:
        condition: Name of condition (sepsis, stroke, stemi, anaphylaxis, pe).

    Returns:
        Dictionary with screening criteria and thresholds.
    """
    conditions = {
        "sepsis": {
            "name": "Sepsis (qSOFA)",
            "criteria": [
                "Altered mental status (GCS < 15)",
                "Respiratory rate >= 22",
                "Systolic BP <= 100 mmHg",
            ],
            "threshold": "2 or more criteria = positive screen",
            "additional_signs": [
                "Temperature > 101.3F or < 96.8F",
                "Heart rate > 90 with suspected infection",
                "Lactate > 2 mmol/L",
                "WBC > 12k or < 4k",
            ],
            "time_window": "Sepsis bundle within 1 hour",
        },
        "stroke": {
            "name": "Stroke (BE-FAST)",
            "criteria": [
                "Balance - sudden loss of balance/coordination",
                "Eyes - sudden vision change in one or both eyes",
                "Face - facial droop (asymmetric smile)",
                "Arms - arm drift or weakness",
                "Speech - slurred or abnormal speech",
                "Time - note exact onset time",
            ],
            "threshold": "Any 1 criterion = activate stroke team",
            "time_window": "tPA within 4.5 hours, thrombectomy within 24 hours",
        },
        "stemi": {
            "name": "STEMI / Acute Coronary Syndrome",
            "criteria": [
                "Chest pain/pressure with radiation to arm/jaw/back",
                "Diaphoresis with chest discomfort",
                "Shortness of breath with chest pain",
                "New onset of nausea/vomiting with chest pain",
            ],
            "threshold": "High clinical suspicion = activate cath lab",
            "time_window": "Door-to-balloon < 90 minutes",
        },
        "anaphylaxis": {
            "name": "Anaphylaxis",
            "criteria": [
                "Rapid onset after allergen exposure",
                "Airway compromise (stridor, wheezing, throat tightness)",
                "Hypotension (SBP < 90 or > 30% drop)",
                "Skin involvement (urticaria, angioedema) + respiratory/CV",
            ],
            "threshold": "2 organ systems involved = anaphylaxis",
            "time_window": "Epinephrine immediately",
        },
        "pe": {
            "name": "Pulmonary Embolism",
            "criteria": [
                "Sudden onset dyspnea",
                "Pleuritic chest pain",
                "Tachycardia unexplained by other cause",
                "Recent immobilization or surgery",
                "Unilateral leg swelling",
                "Hemoptysis",
            ],
            "threshold": "Wells score >= 4 or high clinical suspicion",
            "time_window": "Anticoagulation within hours",
        },
    }
    key = condition.lower().replace(" ", "_")
    return conditions.get(key, {"error": f"Unknown condition: {condition}"})


esi_criteria_tool = FunctionTool(func=lookup_esi_criteria)
red_flag_criteria_tool = FunctionTool(func=lookup_red_flag_criteria)
