PROMPT_VERSION = "v2.3"

# --- DISC-Based Generative Leadership Question Framework -------------------
# Per the "DISC-Based Generative Question Framework for Generative Leadership
# & Behavioural Profiling" spec: every question is built by combining a
# leadership COMPETENCY + a leadership CONTEXT + a behavioural TRIGGER, then
# each of the 4 required answer options is written in a distinct DISC style
# (D/I/S/C) reflecting that style's known blind spot for this exact scenario
# — so a single question simultaneously classifies DISC style and probes a
# specific leadership competency, without needing a separate DISC-detection
# phase before question generation.

LEADERSHIP_COMPETENCIES: list[str] = [
    "Situational Leadership", "Decision Making", "Problem Solving",
    "Communication", "Conflict Management", "Delegation & Empowerment",
    "Performance Management", "Change & Adaptability",
    "Influencing & Stakeholder Management", "Team Dynamics",
    "Pressure & Stress Response", "Emotional Regulation",
    "Leadership Presence", "Strategic Thinking", "Innovation & Risk",
    "Accountability & Ownership", "Collaboration", "Coaching & Development",
    "Customer / Stakeholder Orientation", "Ethical & Values-Based Decisions",
]

LEADERSHIP_CONTEXTS: list[str] = [
    "Managing direct reports", "Managing peers", "Managing upwards",
    "Cross-functional collaboration", "Client / customer interactions",
    "Senior stakeholder interactions", "Crisis situations",
    "High-pressure situations", "Organisational change", "Team conflict",
    "Performance issues", "Business-critical decisions",
]

BEHAVIOURAL_TRIGGERS: list[str] = [
    "Time pressure", "Ambiguity", "Conflict", "Resistance", "Failure",
    "Uncertainty", "Change", "Competing priorities", "Difficult stakeholder",
    "Emotional situation", "Poor performance", "Ethical dilemma",
    "Unexpected information", "Lack of resources", "Team disagreement",
]

QUESTION_FORMATS: list[str] = [
    "situational_response", "first_action", "behavioural_choice",
    "adaptive_choice", "ranking", "reflection", "self_awareness",
]

# Framework difficulty tiers 1-4 map onto the existing easy/medium/hard/expert
# DB constraint so no schema migration is needed for this dimension.
DIFFICULTY_TIER_TO_LEVEL: dict[str, int] = {
    "easy": 1, "medium": 2, "hard": 3, "expert": 4,
}

DISC_BLIND_SPOT_ANGLES: dict[str, str] = {
    "D": "impatience, speed of decision-making, control, assertiveness, "
         "risk-taking, delegation, listening, handling resistance, "
         "tolerance for slower team members",
    "I": "persuasion, relationship orientation, enthusiasm, recognition, "
         "difficult conversations, follow-through, attention to detail, "
         "managing over-optimism, handling rejection",
    "S": "harmony, patience, resistance to sudden change, conflict "
         "avoidance, supporting others, decision-making under pressure, "
         "assertiveness, managing difficult performance conversations",
    "C": "analysis, quality orientation, perfectionism, decision speed, "
         "risk, ambiguity, delegation, excessive reliance on data, "
         "managing situations where information is incomplete",
}

SYSTEM_PROMPT = (
    "You are the Question Generation Agent for a DISC-based generative "
    "leadership & behavioural profiling assessment. EVERY question you "
    "generate is category 'DISC' — this is a behavioural assessment, never "
    "a technical, skill, or knowledge test. "
    "Generate the COMPLETE question set for this candidate in one pass. Never "
    "repeat or closely paraphrase any question already generated for this "
    "org's question-fingerprint history. Match the difficulty level supplied. "
    "IMPORTANT: the input's overall job difficulty_level (junior/mid/senior/"
    "executive) is a DIFFERENT field from each question's own 'difficulty' "
    "value. Each question's 'difficulty' MUST be exactly one of: easy, medium, "
    "hard, expert — never reuse the job difficulty_level word (e.g. never "
    "output 'mid'; use 'medium' instead). "
    "target_competencies MUST only contain values from the fixed competency "
    "vocabulary provided in the tool schema. "
    "\n\nGENERATION LOGIC — the user message assigns a specific "
    "competency_area and leadership_context to each question number via "
    "assigned_dimensions; you MUST use exactly those, per question, in "
    "order — this is not a free choice. For each question also pick "
    f"ONE-OR-MORE behavioural_trigger values from {BEHAVIOURAL_TRIGGERS} "
    "that fit naturally with its assigned competency_area and "
    "leadership_context. Combine them into a realistic, concrete "
    "workplace scenario at the requested difficulty tier: tier 1 (easy) is a "
    "straightforward situation requiring a behavioural response; tier 2 "
    "(medium) involves competing priorities or differing stakeholder "
    "expectations; tier 3 (hard) has multiple variables, conflicting "
    "interests and incomplete information; tier 4 (expert) is a high-"
    "ambiguity leadership challenge involving business impact, people "
    "dynamics, pressure and competing priorities. "
    f"Also pick a question_format from {QUESTION_FORMATS} that fits the "
    "scenario (e.g. 'first_action' asks what they would do first; "
    "'adaptive_choice' asks which response would be most EFFECTIVE even if "
    "not their natural instinct; 'self_awareness' asks what their team "
    "would likely experience from their response). "
    "\n\nSTRICT FORMAT for every question: write the scenario, then give "
    "EXACTLY 4 options — never 3, never 5. Each option is a DIFFERENT ACTION "
    "the candidate could take IN THAT SPECIFIC SCENARIO, and each option "
    "must be written from the lens of one DISC style's natural blind spot "
    "for THIS competency+context+trigger combination, not a generic DISC "
    "trait: "
    f"Dominance option should probe: {DISC_BLIND_SPOT_ANGLES['D']}. "
    f"Influence option should probe: {DISC_BLIND_SPOT_ANGLES['I']}. "
    f"Steadiness option should probe: {DISC_BLIND_SPOT_ANGLES['S']}. "
    f"Conscientiousness option should probe: {DISC_BLIND_SPOT_ANGLES['C']}. "
    "Do not label the options with D/I/S/C — only phrase them so each one "
    "reflects one style; the behavior-analysis step infers the candidate's "
    "style from which option they pick, and the developmental report later "
    "identifies which situations that natural tendency helps or hinders in — "
    "never frame any option as objectively 'right' or 'wrong', good or bad. "
    "CRITICAL: all 4 options must be genuinely professional, defensible "
    "responses that a competent, well-intentioned employee could plausibly "
    "choose — they differ ONLY in behavioural style, never in competence or "
    "integrity. NEVER include an option depicting unprofessional, unethical, "
    "or clearly inferior conduct (e.g. blaming a colleague, hiding a "
    "mistake, ignoring a problem, avoiding responsibility) — those are not "
    "DISC-style trade-offs, they are just bad answers, and must never appear "
    "as one of the 4 options. If a Steadiness/Conscientiousness angle would "
    "otherwise read as passive or avoidant, rewrite it as a considered, "
    "deliberate choice instead (e.g. 'seek to understand root causes before "
    "acting' rather than 'do nothing and hope it resolves itself'). "
    "\n\nNEVER generate generic self-rating or self-assessment options such as "
    "'I have no experience' / 'I have some experience' / 'I have a lot of "
    "experience', or any option that ranks/grades the candidate on a scale — "
    "these are NOT DISC options and must never appear. Every option must be a "
    "concrete ACTION taken in response to the scenario, not a self-description. "
    "\n\nVARIETY ACROSS THE SET — HARD LIMIT: assigned_dimensions already "
    "guarantees each question uses a different competency_area and "
    "leadership_context label, but that is NOT enough on its own — the "
    "underlying STORYLINE must also be unique across the whole set. Several "
    "different competency_area labels (e.g. Performance Management, "
    "Coaching & Development, Accountability & Ownership, Team Dynamics) can "
    "all still tempt you toward the SAME storyline of 'a team member is "
    "underperforming/struggling/missing deadlines' — you MUST NOT do this "
    "more than ONCE in the entire set, no matter which competency labels "
    "are assigned to those questions. The same hard limit of ONCE PER SET "
    "applies to every one of these storyline archetypes, regardless of "
    "which competency_area or leadership_context they're assigned to: "
    "(1) a team member is underperforming/struggling/missing deadlines/"
    "overwhelmed, "
    "(2) you are new to a role/responsibility and feel unprepared, "
    "(3) the organisation/team is undergoing structural or workflow change "
    "(restructuring, merger, new technology, new process), "
    "(4) two team members are in conflict with each other, "
    "(5) a stakeholder/client is unhappy or a crisis has occurred, "
    "(6) you must make a high-stakes decision under uncertainty. "
    "Before finalizing your output, mentally audit the full set of "
    "target_question_count scenarios against this list of 6 archetypes — if "
    "any archetype appears more than once, rewrite the later occurrence(s) "
    "into a genuinely different storyline (still using its assigned "
    "competency_area and leadership_context) before returning your answer."
)

# Maps PRD category names to lowercase competency key aliases for weight lookup.
CATEGORY_TO_COMPETENCY: dict[str, str] = {
    "Technical": "technical",
    "Behavioral": "behavioral",
    "Leadership": "leadership",
    "Case Study": "case_study",
    "Scenario": "scenario",
    "Decision-Making": "decision_making",
    "Conflict Resolution": "conflict_resolution",
    "Problem Solving": "problem_solving",
    "Analytical": "analytical",
    "Situational Judgment": "situational_judgment",
    "Communication": "communication",
    "Ethics": "ethics",
    "Innovation": "innovation",
    "Culture Fit": "culture_fit",
    "Stress": "stress",
    "Priority Management": "priority_management",
    "Negotiation": "negotiation",
    "Business Strategy": "business_strategy",
    "Financial": "financial",
    "Presentation": "presentation",
    "Customer Handling": "customer_handling",
    "DISC": "disc",
}

VALID_CATEGORIES = list(CATEGORY_TO_COMPETENCY.keys())
VALID_COMPETENCIES = sorted(set(CATEGORY_TO_COMPETENCY.values()))

QUESTION_GENERATION_TOOL: dict = {
    "name": "generate_question_set",
    "description": "Generate a complete personalized question set for the candidate.",
    "input_schema": {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "category": {"type": "string", "enum": VALID_CATEGORIES},
                        "target_competencies": {
                            "type": "array",
                            "items": {"type": "string", "enum": ["disc"]},
                            "description": "Always exactly ['disc'] — every question in this assessment is DISC.",
                        },
                        "difficulty": {
                            "type": "string",
                            "enum": ["easy", "medium", "hard", "expert"],
                        },
                        "answer_format": {
                            "type": "string",
                            "enum": ["multiple_choice"],
                        },
                        "options": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 4,
                            "maxItems": 4,
                            "description": (
                                "EXACTLY 4 options — one per DISC style (Dominance/Influence/"
                                "Steadiness/Conscientiousness), each a concrete action in the "
                                "scenario, never a self-rating."
                            ),
                        },
                        "resume_reference": {
                            "type": "boolean",
                            "description": "True if this question directly cites the candidate's resume.",
                        },
                        "competency_area": {
                            "type": "string",
                            "enum": LEADERSHIP_COMPETENCIES,
                            "description": "Which of the 20 leadership competencies this question probes.",
                        },
                        "leadership_context": {
                            "type": "string",
                            "enum": LEADERSHIP_CONTEXTS,
                            "description": "Which leadership situation this scenario is set in.",
                        },
                        "behavioural_triggers": {
                            "type": "array",
                            "items": {"type": "string", "enum": BEHAVIOURAL_TRIGGERS},
                            "description": "One or more behavioural triggers present in the scenario.",
                        },
                        "question_format": {
                            "type": "string",
                            "enum": QUESTION_FORMATS,
                            "description": "The response-mode framing of the question.",
                        },
                    },
                    "required": [
                        "question", "category", "target_competencies",
                        "difficulty", "answer_format", "options", "resume_reference",
                        "competency_area", "leadership_context",
                        "behavioural_triggers", "question_format",
                    ],
                },
            }
        },
        "required": ["questions"],
    },
}
