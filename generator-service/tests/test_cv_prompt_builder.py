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
