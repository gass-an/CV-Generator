import re

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from cv_generator_shared.llm_models import LlmConfiguration

LLM_CONFIGURATION_ID = 1
LLM_CONFIGURATION_LOCK_ID = 0x4356474C4C4D
HF_MODEL_REFERENCE = re.compile(
    r"\A(?P<owner>[A-Za-z0-9](?:[A-Za-z0-9._-]{0,95}))/(?P<repo>"
    r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,191})):(?P<quant>"
    r"[A-Za-z0-9][A-Za-z0-9._-]{0,63})\Z"
)


def normalize_hf_model_reference(value: str) -> str:
    """Valide le sous-ensemble sûr owner/repository:quantification de llama.cpp."""
    normalized = value.strip()
    if len(normalized) > 255 or HF_MODEL_REFERENCE.fullmatch(normalized) is None:
        raise ValueError(
            "Référence invalide. Utilisez organisation/modele-GGUF:quantification."
        )
    return normalized


async def lock_llm_configuration(session: AsyncSession) -> None:
    """Sérialise création/réservation de jobs et changements de modèle."""
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:lock_id)"),
        {"lock_id": LLM_CONFIGURATION_LOCK_ID},
    )


async def get_or_create_llm_configuration(
    session: AsyncSession, *, fallback_model: str
) -> LlmConfiguration:
    fallback = normalize_hf_model_reference(fallback_model)
    configuration = await session.get(LlmConfiguration, LLM_CONFIGURATION_ID)
    if configuration is None:
        configuration = LlmConfiguration(
            id=LLM_CONFIGURATION_ID, selected_model=fallback
        )
        session.add(configuration)
        await session.flush()
    return configuration


async def get_llm_configuration_for_update(
    session: AsyncSession, *, fallback_model: str
) -> LlmConfiguration:
    await lock_llm_configuration(session)
    statement = (
        select(LlmConfiguration)
        .where(LlmConfiguration.id == LLM_CONFIGURATION_ID)
        .with_for_update()
    )
    configuration = (await session.execute(statement)).scalar_one_or_none()
    if configuration is None:
        configuration = await get_or_create_llm_configuration(
            session, fallback_model=fallback_model
        )
    return configuration
