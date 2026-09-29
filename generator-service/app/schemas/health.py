from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """État minimal indiquant que l'API répond."""

    status: Literal["ok"]
