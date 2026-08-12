_SECTION_15_EXCLUSION = (
    "Do not infer, mention, score, or reference anything related to age, gender, "
    "race, ethnicity, religion, disability, national origin, physical appearance, "
    "or any other protected characteristic. Do not treat emotional expression as a "
    "hiring criterion."
)

NARRATIVE_SYSTEM_PROMPT = (
    "You are a senior HR analyst writing sections of a DISC personality assessment report. "
    "This is a pure personality/behavioral assessment — every question is a DISC-style workplace "
    "scenario with no objectively correct or incorrect answer. There is no pass/fail verdict, no "
    "numeric hiring score, and no competency grading. Base every statement strictly on the "
    "candidate's DISC classification (primary/secondary style, confidence, rationale) and the "
    "behavioral patterns evident in their answers — never invent or reference a hire/reject "
    "decision, a numeric score, or competency correctness. "
    "Every strength and weakness bullet MUST include a direct quote from the candidate's answer, "
    "formatted as: '…(cited from Q{n}: \"…excerpt…\")'. "
    "CRITICAL ACCURACY RULE: the Q{n} you cite MUST be the exact question number whose answer "
    "actually contains that quoted excerpt, and the claim in the bullet MUST be genuinely "
    "supported by that specific quote — never attach a quote from one question to a claim about "
    "a different topic, and never cite a Q number whose answer does not contain the quoted text. "
    "Before finalizing each bullet, re-check that the cited Q{n} and the quoted text match the "
    "answer excerpts given in the input. "
    "Never invent quotes or information not present in the input. "
    "The final_verdict field must be a full paragraph summarizing the candidate's DISC profile and "
    "what it suggests about their working style — never a hire/reject label or score reference. "
    + _SECTION_15_EXCLUSION
)

NARRATIVE_TOOL = {
    "name": "generate_report_narrative",
    "description": "Write all narrative prose sections of the hiring report.",
    "input_schema": {
        "type": "object",
        "properties": {
            "executive_summary": {
                "type": "string",
                "description": (
                    "2-3 sentences. State the candidate's primary and secondary DISC style and "
                    "what it means for how they work. Never state a hire/reject verdict or score."
                ),
            },
            "candidate_overview": {
                "type": "string",
                "description": "2-3 sentences on the candidate's background, from the resume.",
            },
            "resume_summary": {
                "type": "string",
                "description": "3-4 sentences summarising key experience from the parsed resume.",
            },
            "interview_summary": {
                "type": "string",
                "description": (
                    "3-4 sentences on the candidate's overall behavioral/DISC pattern across the "
                    "workplace-scenario questions — not a performance or correctness summary."
                ),
            },
            "culture_fit": {
                "type": "string",
                "description": "2-3 sentences on how the candidate's DISC style aligns with org culture values provided.",
            },
            "domain_knowledge": {
                "type": "string",
                "description": (
                    "2-3 sentences on domain background evidenced in the resume summary. "
                    "If no domain-specific answers exist (pure DISC assessment), state that "
                    "explicitly and note this report focuses on behavioral style, not domain skill."
                ),
            },
            "skill_gap_analysis": {
                "type": "string",
                "description": (
                    "Paragraph on any behavioral working-style considerations for this role, based "
                    "on the DISC profile — not a skill or score gap analysis, since none exists here."
                ),
            },
            "strengths": {
                "type": "array",
                "description": "2-4 behavioral strength bullets tied to the DISC style. Each MUST cite a quoted answer excerpt.",
                "minItems": 2,
                "maxItems": 4,
                "items": {"type": "string"},
            },
            "weaknesses": {
                "type": "array",
                "description": (
                    "2-4 behavioral watch-out bullets tied to the DISC style (e.g. blind spots "
                    "typical of that style) — never a skill deficiency. Each MUST cite a quoted "
                    "answer excerpt."
                ),
                "minItems": 2,
                "maxItems": 4,
                "items": {"type": "string"},
            },
            "potential_risks": {
                "type": "string",
                "description": "Paragraph on team/role friction risks suggested by the DISC style and integrity flags — never score-based.",
            },
            "learning_curve_estimate": {
                "type": "string",
                "description": "2-3 sentences on how the candidate's DISC style tends to approach ramping up on a new role.",
            },
            "management_readiness": {
                "type": "string",
                "description": "2-3 sentences on management/leadership tendencies suggested by the DISC style — never based on a leadership score.",
            },
            "promotion_potential": {
                "type": "string",
                "description": "2-3 sentences on long-term working-style trajectory suggested by the DISC profile.",
            },
            "integrity_summary_prose": {
                "type": "string",
                "description": (
                    "Human-readable summary of integrity flags. If risk is low or no flags, "
                    "state 'No integrity concerns identified.' "
                    "Never suggest automatic rejection — human makes the call."
                ),
            },
            "final_verdict": {
                "type": "string",
                "description": (
                    "Full paragraph summarizing the candidate's DISC profile (primary/secondary "
                    "style, confidence) and what it suggests about their working style and fit. "
                    "Never a hire/reject label, never a numeric score reference."
                ),
            },
        },
        "required": [
            "executive_summary", "candidate_overview", "resume_summary", "interview_summary",
            "culture_fit", "domain_knowledge", "skill_gap_analysis", "strengths", "weaknesses",
            "potential_risks", "learning_curve_estimate", "management_readiness",
            "promotion_potential", "integrity_summary_prose", "final_verdict",
        ],
    },
}

DEVELOPMENTAL_SYSTEM_PROMPT = (
    "You are a leadership development coach writing the developmental-insight section of a "
    "DISC-based behavioural profiling report. Per the DISC-Based Generative Leadership Question "
    "Framework: this section must NEVER label the candidate as a 'type of leader', and must NEVER "
    "judge their natural tendency as good or bad. Instead, for each insight, identify the natural "
    "behavioural tendency and frame it as: 'this is your natural tendency — in which situations "
    "does it help you, and in which situations might you need to adapt?' Base every statement on "
    "the candidate's DISC profile and their answers to the leadership-scenario questions, "
    "distinguishing (where evident from the answers) between their NATURAL response and their "
    "ADAPTIVE/most-effective response to the same scenario. "
    "\n\nCONSISTENCY RULE: every claim you write — natural tendencies, strengths, blind spots, "
    "communication/conflict/decision-making style — MUST be logically consistent with the "
    "candidate's stated PRIMARY and SECONDARY DISC style given in the input. Before writing each "
    "claim, check that it matches the known behavioural profile of that style and does not "
    "contradict a claim already made elsewhere in this same output. In particular: a "
    "Dominance-primary candidate should be described as direct/assertive/confrontational, NEVER "
    "as naturally diplomatic or conflict-avoidant (that is a Steadiness trait); an "
    "Influence-primary candidate should be described as relationship-focused/persuasive, NEVER as "
    "naturally data-driven or process-focused (that is a Conscientiousness trait); a "
    "Steadiness-primary candidate should be described as patient/consensus-seeking, NEVER as "
    "naturally confrontational or fast-decision-making (that is a Dominance trait); a "
    "Conscientiousness-primary candidate should be described as analytical/detail-oriented, NEVER "
    "as naturally spontaneous or relationship-first (that is an Influence trait). If the "
    "candidate's answers show a genuine mix of styles, attribute each specific tendency to "
    "whichever of their two styles (primary or secondary) actually explains it — do not blend "
    "them into a single contradictory claim. "
    + _SECTION_15_EXCLUSION
)

DEVELOPMENTAL_TOOL = {
    "name": "generate_developmental_insights",
    "description": (
        "Generate the non-judgmental developmental-insight output required by the DISC-Based "
        "Generative Leadership Question Framework (section 11)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "natural_leadership_tendencies": {
                "type": "string",
                "description": "2-3 sentences on the candidate's natural (instinctive) leadership tendency, per their DISC style.",
            },
            "behavioural_strengths": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 2,
                "maxItems": 4,
                "description": "Situations where the natural tendency helps them.",
            },
            "potential_blind_spots": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 2,
                "maxItems": 4,
                "description": "Situations where the natural tendency might work against them — framed as 'may need to adapt', never as a flaw.",
            },
            "behaviour_under_pressure": {
                "type": "string",
                "description": "2-3 sentences on how this DISC style tends to respond under time pressure, ambiguity, or conflict.",
            },
            "communication_preferences": {
                "type": "string",
                "description": "1-2 sentences on this style's natural communication tendency.",
            },
            "conflict_tendencies": {
                "type": "string",
                "description": "1-2 sentences on this style's natural response to disagreement or confrontation.",
            },
            "decision_making_tendencies": {
                "type": "string",
                "description": "1-2 sentences on this style's natural decision-making pace and approach.",
            },
            "adaptability_assessment": {
                "type": "string",
                "description": (
                    "1-2 sentences assessing, from the evidence available, how well the "
                    "candidate can consciously adapt their natural response toward a more "
                    "effective one when the situation calls for it — never a numeric score."
                ),
            },
            "areas_for_behavioural_development": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "maxItems": 3,
                "description": "1-3 coaching-style development suggestions tied to the identified blind spots.",
            },
        },
        "required": [
            "natural_leadership_tendencies", "behavioural_strengths", "potential_blind_spots",
            "behaviour_under_pressure", "communication_preferences", "conflict_tendencies",
            "decision_making_tendencies", "adaptability_assessment",
            "areas_for_behavioural_development",
        ],
    },
}

STRUCTURED_SYSTEM_PROMPT = (
    "You are a senior HR analyst completing the structured data sections of a DISC personality "
    "assessment report. Use the narrative context and DISC profile provided — there is no "
    "competency score data in this assessment type. Be specific and consistent with the narrative. "
    + _SECTION_15_EXCLUSION
)

STRUCTURED_TOOL = {
    "name": "generate_report_structured",
    "description": "Write structured data sections: scores with benchmarks, questions, training needs.",
    "input_schema": {
        "type": "object",
        "properties": {
            "recommended_next_round": {
                "type": "string",
                "description": "E.g. 'Technical Panel Interview' or 'Final HR Round'.",
            },
            "training_needs_detailed": {
                "type": "array",
                "description": "1-3 development areas with priority, suggested by the DISC style's typical blind spots.",
                "minItems": 1,
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "properties": {
                        "area": {"type": "string"},
                        "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                        "rationale": {"type": "string"},
                    },
                    "required": ["area", "priority", "rationale"],
                },
            },
            "suggested_hr_questions": {
                "type": "array",
                "description": "3 HR-round questions to further explore the candidate's DISC style and working preferences.",
                "minItems": 3,
                "maxItems": 3,
                "items": {"type": "string"},
            },
            "suggested_ceo_questions": {
                "type": "array",
                "description": "3 CEO-round questions on strategic fit and leadership style, informed by the DISC profile.",
                "minItems": 3,
                "maxItems": 3,
                "items": {"type": "string"},
            },
        },
        "required": [
            "recommended_next_round",
            "training_needs_detailed",
            "suggested_hr_questions",
            "suggested_ceo_questions",
        ],
    },
}
