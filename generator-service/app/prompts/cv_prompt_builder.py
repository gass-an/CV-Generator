import json
from importlib import resources
from string import Template
from typing import Any

from app.clients.avp_client import AvpData
from app.clients.llm_client import ChatMessage


class CvPromptBuilder:
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
