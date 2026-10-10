import copy
import json

from app.clients.avp_client import AvpData
from app.prompts.cover_letter_prompt_builder import CoverLetterPromptBuilder


def build_messages() -> tuple[list[dict[str, str]], dict[str, object], AvpData]:
    resume: dict[str, object] = {
        "basics": {
            "name": "Élodie Exemple",
            "summary": "Texte littéral ${AVP_JOB_POSTING}",
        },
        "skills": [{"name": "Sécurité"}],
    }
    avp = AvpData(
        reference="3134-26-1382/SR",
        content="# Missions\n- Administrer les systèmes",
        source_url="https://opt.example/index.md",
        is_archived=False,
    )
    return CoverLetterPromptBuilder().build(resume_data=resume, avp=avp), resume, avp


def test_build_injects_separate_sources_once_without_mutating_them() -> None:
    messages, resume, avp = build_messages()
    original_resume = copy.deepcopy(resume)

    assert [message["role"] for message in messages] == ["system", "user"]
    user_prompt = messages[1]["content"]
    candidate_json = user_prompt.split("<CANDIDATE_JSON_RESUME>\n", 1)[1].split(
        "\n</CANDIDATE_JSON_RESUME>", 1
    )[0]
    assert json.loads(candidate_json) == resume
    assert '"summary": "Texte littéral ${AVP_JOB_POSTING}"' in candidate_json
    assert "\\u00c9" not in candidate_json
    assert avp.content in user_prompt
    assert resume == original_resume


def test_system_prompt_requires_fidelity_asciidoc_and_structural_examples() -> None:
    messages, _, _ = build_messages()
    system_prompt = messages[0]["content"]

    assert "JSON Resume est l'unique source" in system_prompt
    assert "N'invente jamais une expérience" in system_prompt
    assert "présente uniquement dans l'AVP en fait candidat" in system_prompt
    assert "format AsciiDoc" in system_prompt
    assert "« **texte** », « - élément », « # Titre »" in system_prompt
    assert "espaces en fin de ligne" in system_prompt
    assert "*mot en gras*" in system_prompt
    assert "** Sous-élément" in system_prompt
    assert "exclusivement syntaxique et structurel" in system_prompt
    assert "aucune donnée, phrase ou formulation" in system_prompt
    assert "<coordonnées disponibles du candidat>" in system_prompt
    assert "<paragraphe reliant uniquement des faits candidat réels" in system_prompt
    assert "Prénom Nom issu du JSON Resume" not in system_prompt
