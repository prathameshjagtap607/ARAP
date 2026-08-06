import uuid
from unittest.mock import patch

import pytest

from agents.question_generation.prompts import PROMPT_VERSION
from tests.question_sets.conftest import FAKE_EMBEDDINGS, FAKE_QUESTIONS


def test_derive_category_counts_is_always_all_disc():
    from src.modules.question_sets.service import _derive_category_counts

    counts = _derive_category_counts({"leadership": 100.0}, target=10)

    assert counts == {"DISC": 10}


def test_derive_category_counts_all_disc_regardless_of_selected_competency():
    from src.modules.question_sets.service import _derive_category_counts

    counts = _derive_category_counts({"technical": 100.0}, target=10)

    assert counts == {"DISC": 10}


def test_derive_category_counts_all_disc_with_multiple_competencies():
    from src.modules.question_sets.service import _derive_category_counts

    counts = _derive_category_counts({"technical": 50.0, "leadership": 50.0}, target=10)

    assert counts == {"DISC": 10}


def test_resolve_competency_names_maps_uuid_keys_to_names(db, seed):
    from src.models.competency_library import CompetencyLibrary
    from src.modules.question_sets.service import _resolve_competency_names

    org = seed["job"].org_id
    admin_id = seed["job"].created_by
    entry = CompetencyLibrary(org_id=org, name="Leadership", created_by=admin_id)
    db.add(entry)
    db.flush()

    resolved = _resolve_competency_names(db, org, {str(entry.id): 100.0})

    assert resolved == {"Leadership": 100.0}


def test_resolve_competency_names_passes_through_plain_names(db, seed):
    from src.modules.question_sets.service import _resolve_competency_names

    org = seed["job"].org_id
    resolved = _resolve_competency_names(db, org, {"technical": 70.0, "leadership": 30.0})

    assert resolved == {"technical": 70.0, "leadership": 30.0}


def test_resolve_competency_names_drops_unknown_uuid(db, seed):
    from src.modules.question_sets.service import _resolve_competency_names

    org = seed["job"].org_id
    resolved = _resolve_competency_names(db, org, {str(uuid.uuid4()): 100.0})

    assert resolved == {}


def test_generate_persists_question_set(db, seed, mock_agent, mock_embed):
    from src.modules.question_sets.service import generate_question_set

    result = generate_question_set(db, seed["session"].id, seed["org"].id, target=2)

    assert result.session_id == seed["session"].id
    assert result.locked_at is not None
    assert result.generation_prompt_version == PROMPT_VERSION
    assert len(result.questions) == 2
    assert result.questions[0].sequence_no == 1
    assert result.questions[1].sequence_no == 2


def test_generate_rejects_duplicate_above_threshold(db, seed):
    from src.models.question_fingerprints import QuestionFingerprint
    from src.modules.question_sets.service import generate_question_set

    # Pre-insert a fingerprint nearly identical to FAKE_QUESTIONS[0] (cosine sim ≈ 1.0)
    near_identical = [v + 0.000001 for v in FAKE_EMBEDDINGS[0]]
    fp = QuestionFingerprint(
        org_id=seed["org"].id,
        question_text="Near-duplicate of question 0",
        question_embedding=near_identical,
    )
    db.add(fp)
    db.commit()

    # embed_texts returns FAKE_EMBEDDINGS for pass 1 (2 questions) and
    # FAKE_EMBEDDINGS[1:] for pass 2 (gap fill)
    emb_calls = [FAKE_EMBEDDINGS, [FAKE_EMBEDDINGS[1]]]
    call_idx = [0]

    def fake_embed(texts):
        idx = call_idx[0]
        call_idx[0] += 1
        return emb_calls[idx] if idx < len(emb_calls) else [FAKE_EMBEDDINGS[1]]

    # agent returns 2 questions on pass 1 (q0 is duplicate), then 1 on pass 2
    agent_calls = [FAKE_QUESTIONS, [FAKE_QUESTIONS[1]]]
    agent_idx = [0]

    def fake_agent(**kwargs):
        idx = agent_idx[0]
        agent_idx[0] += 1
        return agent_calls[idx] if idx < len(agent_calls) else [FAKE_QUESTIONS[1]]

    with patch("src.modules.question_sets.service.run_question_generation_agent", side_effect=lambda **kw: fake_agent(**kw)), \
         patch("src.modules.question_sets.service.embed_texts", side_effect=fake_embed):
        # target=1: q0 is rejected (similarity >= 0.92), q1 is accepted -> 1 question
        result = generate_question_set(db, seed["session"].id, seed["org"].id, target=1)

    assert len(result.questions) == 1
    assert result.questions[0].question == FAKE_QUESTIONS[1]["question"]


def test_generate_accepts_below_threshold(db, seed, mock_agent):
    from src.models.question_fingerprints import QuestionFingerprint
    from src.modules.question_sets.service import generate_question_set

    # Pre-insert a fingerprint very different from both fake embeddings (orthogonal)
    orthogonal = [0.0] * 1535 + [1.0]
    fp = QuestionFingerprint(
        org_id=seed["org"].id,
        question_text="Unrelated question",
        question_embedding=orthogonal,
    )
    db.add(fp)
    db.commit()

    with patch("src.modules.question_sets.service.embed_texts", return_value=FAKE_EMBEDDINGS):
        result = generate_question_set(db, seed["session"].id, seed["org"].id, target=2)

    assert len(result.questions) == 2


def test_generate_raises_lookup_when_session_not_found(db, seed):
    from src.modules.question_sets.service import generate_question_set

    with pytest.raises(LookupError, match="session"):
        generate_question_set(db, uuid.uuid4(), seed["org"].id)


def test_generate_raises_value_error_when_no_candidate_profile(db, seed, mock_agent, mock_embed):
    from src.models.assessment_sessions import AssessmentSession
    from src.modules.question_sets.service import generate_question_set

    session = db.query(AssessmentSession).filter_by(id=seed["session"].id).first()
    original = session.candidate_profile_id
    session.candidate_profile_id = None
    db.commit()

    try:
        with pytest.raises(ValueError, match="Candidate profile"):
            generate_question_set(db, seed["session"].id, seed["org"].id)
    finally:
        session.candidate_profile_id = original
        db.commit()


def test_generate_raises_runtime_when_agent_returns_none(db, seed, mock_embed):
    from src.modules.question_sets.service import generate_question_set

    with patch("src.modules.question_sets.service.run_question_generation_agent", return_value=None), pytest.raises(RuntimeError, match="agent"):
        generate_question_set(db, seed["session"].id, seed["org"].id)


def test_get_raises_lookup_when_not_generated(db, seed):
    from src.modules.question_sets.service import get_question_set

    with pytest.raises(LookupError):
        get_question_set(db, seed["session"].id, seed["org"].id)


def test_get_returns_set_after_generate(db, seed, mock_agent, mock_embed):
    from src.modules.question_sets.service import (
        generate_question_set,
        get_question_set,
    )

    generate_question_set(db, seed["session"].id, seed["org"].id, target=2)
    result = get_question_set(db, seed["session"].id, seed["org"].id)

    assert len(result.questions) == 2
    assert result.locked_at is not None
