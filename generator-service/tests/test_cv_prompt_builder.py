import copy
import json

from app.clients.avp_client import AvpData
from app.prompts.cv_prompt_builder import CvPromptBuilder


def test_build_keeps_sources_separate_and_unchanged() -> None:
    resume = {
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
    original_resume = copy.deepcopy(resume)
    messages = CvPromptBuilder().build(resume_data=resume, avp=avp)

    assert [message["role"] for message in messages] == ["system", "user"]
    user_prompt = messages[1]["content"]
    assert "<CANDIDATE_JSON_RESUME>" in user_prompt
    assert "</CANDIDATE_JSON_RESUME>" in user_prompt
    assert "<AVP_JOB_POSTING>" in user_prompt
    assert "</AVP_JOB_POSTING>" in user_prompt
    assert '"name": "Élodie Exemple"' in user_prompt
    assert "# Missions\n- Administrer les systèmes" in user_prompt
    assert "\\u00c9" not in user_prompt
    candidate_json = user_prompt.split("<CANDIDATE_JSON_RESUME>\n", 1)[1].split(
        "\n</CANDIDATE_JSON_RESUME>", 1
    )[0]
    assert '"summary": "Texte littéral ${AVP_JOB_POSTING}"' in candidate_json
    assert json.loads(candidate_json) == resume
    assert resume == original_resume
    assert avp.content == "# Missions\n- Administrer les systèmes"


def test_system_prompt_enforces_fidelity_prioritization_and_asciidoc() -> None:
    messages = CvPromptBuilder().build(
        resume_data={"basics": {"name": "Test"}},
        avp=AvpData(
            reference="AVP",
            content="Poste",
            source_url="https://opt.example/index.md",
            is_archived=False,
        ),
    )

    system_prompt = messages[0]["content"]
    assert "directement justifiable par le JSON Resume" in system_prompt
    assert "ne convertis jamais « NC » en « France »" in system_prompt
    assert "provenant uniquement de l'AVP" in system_prompt
    assert "Préserve strictement la nature sémantique" in system_prompt
    assert "Un élément de « interests » ne doit jamais devenir une compétence" in (
        system_prompt
    )
    assert "une mission décrite dans une expérience ne doit jamais devenir" in (
        system_prompt
    )
    assert "conserve ceux qui apportent un détail utile" in system_prompt
    assert "* Outils bureautiques : Word, Excel, PowerPoint" in system_prompt
    assert "Ne transforme pas les « keywords » en compétences indépendantes" in (
        system_prompt
    )
    assert "présente-les en priorité" in system_prompt
    assert "N'augmente jamais artificiellement" in system_prompt
    assert "= Prénom Nom" in system_prompt
    assert "== Compétences" in system_prompt
    assert "=== Intitulé du poste" in system_prompt
    assert "exactement un espace après les signes « = »" in system_prompt
    assert "jamais « ===Diplôme — Établissement »" in system_prompt
    assert "* Compétence réelle" in system_prompt
    assert "**gras**" in system_prompt
    assert "trois backticks" in system_prompt
    assert "noms techniques du JSON Resume" in system_prompt
    assert "aucun texte ni aucune donnée de cet exemple ne doit être recopié" in (
        system_prompt
    )
