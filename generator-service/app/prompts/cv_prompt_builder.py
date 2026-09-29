import json
from importlib import resources
from string import Template
from typing import Any

from app.clients.avp_client import AvpData
from app.clients.llm_client import ChatMessage


class CvPromptBuilder:
    """Construit les messages du LLM pour générer un CV fidèle en AsciiDoc."""

    def __init__(self) -> None:
        prompt_package = resources.files("app.prompts.cv")
        self._system_prompt = prompt_package.joinpath("system.txt").read_text(
            encoding="utf-8"
        )
        self._user_template = prompt_package.joinpath("user.txt").read_text(
            encoding="utf-8"
        )

    def build(
        self,
        *,
        resume_data: dict[str, Any],
        avp: AvpData,
    ) -> list[ChatMessage]:
        """Injecte le JSON Resume et l'AVP séparément, en une seule substitution."""
        serialized_resume = json.dumps(
            resume_data,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        user_prompt = Template(self._user_template).substitute(
            CANDIDATE_JSON_RESUME=serialized_resume,
            AVP_JOB_POSTING=avp.content,
        )
        return [
            {"role": "system", "content": self._system_prompt.strip()},
            {"role": "user", "content": user_prompt.strip()},
        ]
