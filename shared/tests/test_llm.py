import pytest

import cv_generator_shared
from cv_generator_shared.llm import normalize_hf_model_reference


@pytest.mark.parametrize(
    "reference",
    [
        "../model.gguf",
        "https://example.com/model.gguf",
        "org/model",
        "org/model:Q4 K M",
        "org/model:Q4/../../secret",
        "org/model:Q4?url=http://internal",
    ],
)
def test_rejects_unsafe_model_references(reference: str) -> None:
    with pytest.raises(ValueError):
        normalize_hf_model_reference(reference)


def test_normalizes_safe_model_reference() -> None:
    assert (
        normalize_hf_model_reference("  ggml-org/Qwen3-14B-GGUF:Q4_K_M  ")
        == "ggml-org/Qwen3-14B-GGUF:Q4_K_M"
    )


def test_shared_public_exports_remain_backward_compatible() -> None:
    historical = {
        "AdminLoginAttempt",
        "AdminSession",
        "ApiClient",
        "ApiClientData",
        "ApiIdentity",
        "ApiKey",
        "ApiKeyData",
        "ApiKeyWithClientData",
        "ApiKeyService",
        "Base",
        "CreatedApiKey",
        "CreatedClientApiKey",
        "DocumentJob",
        "DocumentJobStatus",
        "DocumentType",
    }
    assert historical | {"LlmConfiguration"} <= set(cv_generator_shared.__all__)
