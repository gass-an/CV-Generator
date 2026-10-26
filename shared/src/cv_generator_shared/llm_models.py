from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from cv_generator_shared.database import Base


class LlmConfiguration(Base):
    """Sélection LLM globale ; la ligne d'identifiant 1 est l'unique configuration."""

    __tablename__ = "llm_configuration"
    __table_args__ = (CheckConstraint("id = 1", name="ck_llm_configuration_singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    selected_model: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
