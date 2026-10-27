import asyncio
import os
import struct
import time
from pathlib import Path

import pytest
from app import llm_metadata
from app.llm_metadata import format_bytes, inspect_model, readable_model_name
from app.llm_router import RouterModel
from app.llm_service import AdminLlmService


def _gguf_string(value: str) -> bytes:
    encoded = value.encode()
    return struct.pack("<Q", len(encoded)) + encoded


def _metadata_value(value_type: int, value: object) -> bytes:
    if value_type == 8:
        return _gguf_string(str(value))
    if value_type == 4:
        return struct.pack("<I", value)
    if value_type == 9:
        element_type, values = value
        encoded = bytearray(struct.pack("<IQ", element_type, len(values)))
        for item in values:
            encoded.extend(_metadata_value(element_type, item))
        return bytes(encoded)
    return bytes(value)


def _write_gguf(
    path: Path, values: dict[str, tuple[int, object]] | None = None
) -> None:
    values = values or {
        "general.architecture": (8, "qwen3"),
        "qwen3.block_count": (4, 40),
        "qwen3.embedding_length": (4, 5120),
        "qwen3.attention.head_count": (4, 40),
        "qwen3.attention.head_count_kv": (4, 8),
    }
    content = bytearray(b"GGUF" + struct.pack("<IQQ", 3, 0, len(values)))
    for key, (value_type, value) in values.items():
        content.extend(_gguf_string(key))
        content.extend(struct.pack("<I", value_type))
        content.extend(_metadata_value(value_type, value))
    path.write_bytes(content + bytes(1024))


def _cached_file(
    cache_root: Path,
    *,
    repository: str = "Qwen3-14B-GGUF",
    revision: str = "revision-a",
    filename: str = "Qwen3-14B-Q4_K_M.gguf",
    blob_name: str = "blob-a",
    values: dict[str, tuple[int, object]] | None = None,
) -> tuple[Path, Path]:
    repository_root = cache_root / f"models--ggml-org--{repository}"
    blobs = repository_root / "blobs"
    snapshot = repository_root / "snapshots" / revision
    blobs.mkdir(parents=True, exist_ok=True)
    snapshot.mkdir(parents=True, exist_ok=True)
    blob = blobs / blob_name
    _write_gguf(blob, values)
    logical = snapshot / filename
    logical.symlink_to(Path("../../blobs") / blob_name)
    return logical, blob


@pytest.fixture(autouse=True)
def clear_metadata_cache() -> None:
    llm_metadata._metadata_cache.clear()


def test_inspects_local_gguf_and_estimates_vram(tmp_path: Path) -> None:
    model = tmp_path / "Qwen3-14B-Q4_K_M.gguf"
    _write_gguf(model)
    info = inspect_model(str(model), cache_root=tmp_path, context_size=8192)
    assert info.size_bytes == model.stat().st_size
    assert info.vram_estimate_bytes is not None
    assert info.vram_estimate_bytes > info.size_bytes


def test_discovers_huggingface_symlink_without_router_path(tmp_path: Path) -> None:
    _logical, blob = _cached_file(tmp_path)
    info = inspect_model(
        None,
        model_id="ggml-org/Qwen3-14B-GGUF:Q4_K_M",
        cache_root=tmp_path,
        context_size=8192,
    )
    assert info.size_bytes == blob.stat().st_size
    assert info.vram_estimate_bytes is not None


def test_router_logical_symlink_to_extensionless_blob_is_accepted(
    tmp_path: Path,
) -> None:
    logical, blob = _cached_file(tmp_path)
    info = inspect_model(str(logical), cache_root=tmp_path, context_size=8192)
    assert info.size_bytes == blob.stat().st_size
    assert info.vram_estimate_bytes is not None


def test_quantization_matching_is_exact_with_multiple_files(tmp_path: Path) -> None:
    _cached_file(
        tmp_path,
        filename="Qwen3-14B-Q4_K_M.gguf",
        blob_name="q4-k-m",
    )
    _logical, q4_zero = _cached_file(
        tmp_path,
        filename="Qwen3-14B-Q4_0.gguf",
        blob_name="q4-zero",
    )
    q4_zero.write_bytes(q4_zero.read_bytes() + b"different-size")

    q4_zero_info = inspect_model(
        None,
        model_id="ggml-org/Qwen3-14B-GGUF:Q4_0",
        cache_root=tmp_path,
        context_size=8192,
    )
    assert q4_zero_info.size_bytes == q4_zero.stat().st_size


def test_discovers_symlinked_multishard_model_without_double_counting(
    tmp_path: Path,
) -> None:
    first, first_blob = _cached_file(
        tmp_path,
        filename="Qwen3-14B-Q4_K_M-00001-of-00002.gguf",
        blob_name="shard-one",
    )
    repository_root = first.parents[2]
    second_blob = repository_root / "blobs" / "shard-two"
    second_blob.write_bytes(b"second shard")
    second = first.parent / "Qwen3-14B-Q4_K_M-00002-of-00002.gguf"
    second.symlink_to(Path("../../blobs/shard-two"))

    info = inspect_model(
        None,
        model_id="ggml-org/Qwen3-14B-GGUF:Q4_K_M",
        cache_root=tmp_path,
        context_size=8192,
    )
    assert info.size_bytes == first_blob.stat().st_size + second_blob.stat().st_size
    assert info.vram_estimate_bytes is not None


def test_incomplete_huggingface_snapshot_is_not_selected(tmp_path: Path) -> None:
    _cached_file(
        tmp_path,
        filename="Qwen3-14B-Q4_K_M-00001-of-00002.gguf",
        blob_name="only-shard",
    )
    info = inspect_model(
        None,
        model_id="ggml-org/Qwen3-14B-GGUF:Q4_K_M",
        cache_root=tmp_path,
        context_size=8192,
    )
    assert info == llm_metadata.ModelStorageInfo(None, None)


def test_distinct_matching_snapshots_are_ambiguous(tmp_path: Path) -> None:
    _cached_file(tmp_path, revision="revision-a", blob_name="blob-a")
    _cached_file(tmp_path, revision="revision-b", blob_name="blob-b")
    info = inspect_model(
        None,
        model_id="ggml-org/Qwen3-14B-GGUF:Q4_K_M",
        cache_root=tmp_path,
        context_size=8192,
    )
    assert info == llm_metadata.ModelStorageInfo(None, None)


def test_snapshots_pointing_to_same_blob_are_deduplicated(tmp_path: Path) -> None:
    first, blob = _cached_file(tmp_path, revision="revision-a", blob_name="shared")
    second_snapshot = first.parents[1] / "revision-b"
    second_snapshot.mkdir()
    (second_snapshot / first.name).symlink_to(Path("../../blobs/shared"))
    info = inspect_model(
        None,
        model_id="ggml-org/Qwen3-14B-GGUF:Q4_K_M",
        cache_root=tmp_path,
        context_size=8192,
    )
    assert info.size_bytes == blob.stat().st_size


def test_discovered_symlink_outside_cache_is_rejected(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    repository = cache / "models--ggml-org--Qwen3-14B-GGUF"
    snapshot = repository / "snapshots" / "revision"
    snapshot.mkdir(parents=True)
    outside = tmp_path / "outside-discovered-gguf"
    _write_gguf(outside)
    (snapshot / "Qwen3-14B-Q4_K_M.gguf").symlink_to(outside)
    info = inspect_model(
        None,
        model_id="ggml-org/Qwen3-14B-GGUF:Q4_K_M",
        cache_root=cache,
        context_size=8192,
    )
    assert info == llm_metadata.ModelStorageInfo(None, None)


def test_replacing_discovered_blob_invalidates_cache(tmp_path: Path) -> None:
    _logical, blob = _cached_file(tmp_path)
    first = inspect_model(
        None,
        model_id="ggml-org/Qwen3-14B-GGUF:Q4_K_M",
        cache_root=tmp_path,
        context_size=8192,
    )
    replacement = blob.with_name("replacement")
    _write_gguf(replacement)
    replacement.write_bytes(replacement.read_bytes() + b"replacement")
    os.replace(replacement, blob)
    second = inspect_model(
        None,
        model_id="ggml-org/Qwen3-14B-GGUF:Q4_K_M",
        cache_root=tmp_path,
        context_size=8192,
    )
    assert second.size_bytes == blob.stat().st_size
    assert second.size_bytes != first.size_bytes


def test_cache_reuses_metadata_and_invalidates_after_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = tmp_path / "model.gguf"
    _write_gguf(model)
    original = llm_metadata._read_gguf_metadata
    reads = 0

    def counted(path: Path) -> dict[str, object]:
        nonlocal reads
        reads += 1
        return original(path)

    monkeypatch.setattr(llm_metadata, "_read_gguf_metadata", counted)
    first = inspect_model(str(model), cache_root=tmp_path, context_size=8192)
    second = inspect_model(str(model), cache_root=tmp_path, context_size=8192)
    assert first == second
    assert reads == 1

    model.write_bytes(model.read_bytes() + b"changed")
    changed = inspect_model(str(model), cache_root=tmp_path, context_size=8192)
    assert changed.size_bytes != first.size_bytes
    assert reads == 2

    model.unlink()
    missing = inspect_model(str(model), cache_root=tmp_path, context_size=8192)
    assert missing == llm_metadata.ModelStorageInfo(None, None)


def test_context_and_gpu_layers_are_part_of_cache_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = tmp_path / "model.gguf"
    _write_gguf(model)
    original = llm_metadata._read_gguf_metadata
    reads = 0

    def counted(path: Path) -> dict[str, object]:
        nonlocal reads
        reads += 1
        return original(path)

    monkeypatch.setattr(llm_metadata, "_read_gguf_metadata", counted)
    baseline = inspect_model(str(model), cache_root=tmp_path, context_size=4096)
    longer = inspect_model(str(model), cache_root=tmp_path, context_size=8192)
    fewer_layers = inspect_model(
        str(model), cache_root=tmp_path, context_size=8192, gpu_layers=10
    )
    assert baseline.vram_estimate_bytes < longer.vram_estimate_bytes
    assert fewer_layers.vram_estimate_bytes < longer.vram_estimate_bytes
    assert reads == 3


def test_complete_multishard_size_and_replacement_invalidation(tmp_path: Path) -> None:
    first = tmp_path / "model-00001-of-00002.gguf"
    second = tmp_path / "model-00002-of-00002.gguf"
    _write_gguf(first)
    second.write_bytes(b"second shard")
    initial = inspect_model(str(first), cache_root=tmp_path, context_size=8192)
    assert initial.size_bytes == first.stat().st_size + second.stat().st_size
    replacement = tmp_path / "replacement.gguf"
    replacement.write_bytes(b"replacement shard with another size")
    os.replace(replacement, second)
    replaced = inspect_model(str(first), cache_root=tmp_path, context_size=8192)
    assert replaced.size_bytes == first.stat().st_size + second.stat().st_size
    assert replaced.size_bytes != initial.size_bytes


def test_incomplete_multishard_is_unavailable(tmp_path: Path) -> None:
    first = tmp_path / "model-00001-of-00002.gguf"
    _write_gguf(first)
    assert inspect_model(
        str(first), cache_root=tmp_path, context_size=8192
    ) == llm_metadata.ModelStorageInfo(None, None)


@pytest.mark.parametrize(
    "content",
    [
        b"invalid",
        b"GGUF" + struct.pack("<I", 99),
        b"GGUF" + struct.pack("<IQQ", 3, 0, 1),
        b"GGUF" + struct.pack("<IQQQ", 3, 0, 1, 2**63),
    ],
)
def test_incomplete_or_malformed_gguf_is_unavailable(
    tmp_path: Path, content: bytes
) -> None:
    model = tmp_path / "invalid.gguf"
    model.write_bytes(content)
    assert inspect_model(
        str(model), cache_root=tmp_path, context_size=8192
    ) == llm_metadata.ModelStorageInfo(None, None)


def test_excessive_array_and_nested_array_are_rejected(tmp_path: Path) -> None:
    excessive = tmp_path / "excessive.gguf"
    header = bytearray(b"GGUF" + struct.pack("<IQQ", 3, 0, 1))
    header.extend(_gguf_string("tokenizer.ggml.tokens"))
    header.extend(struct.pack("<IIQ", 9, 8, llm_metadata.MAX_GGUF_ARRAY_ITEMS + 1))
    excessive.write_bytes(header)
    assert (
        inspect_model(str(excessive), cache_root=tmp_path, context_size=8192).size_bytes
        is None
    )

    nested = tmp_path / "nested.gguf"
    header = bytearray(b"GGUF" + struct.pack("<IQQ", 3, 0, 1))
    header.extend(_gguf_string("nested"))
    header.extend(struct.pack("<IIQI", 9, 9, 1, 4))
    nested.write_bytes(header)
    assert (
        inspect_model(str(nested), cache_root=tmp_path, context_size=8192).size_bytes
        is None
    )


def test_excessive_string_and_unknown_type_are_rejected(tmp_path: Path) -> None:
    excessive = tmp_path / "string.gguf"
    header = bytearray(b"GGUF" + struct.pack("<IQQ", 3, 0, 1))
    header.extend(struct.pack("<Q", llm_metadata.MAX_GGUF_KEY_BYTES + 1))
    excessive.write_bytes(header)
    assert (
        inspect_model(str(excessive), cache_root=tmp_path, context_size=8192).size_bytes
        is None
    )

    unknown = tmp_path / "unknown.gguf"
    header = bytearray(b"GGUF" + struct.pack("<IQQ", 3, 0, 1))
    header.extend(_gguf_string("unknown"))
    header.extend(struct.pack("<I", 99))
    unknown.write_bytes(header)
    assert (
        inspect_model(str(unknown), cache_root=tmp_path, context_size=8192).size_bytes
        is None
    )


def test_outside_path_and_symlink_escape_are_rejected(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    outside = tmp_path / "outside.gguf"
    _write_gguf(outside)
    link = cache / "link.gguf"
    link.symlink_to(outside)
    for path in (outside, link):
        info = inspect_model(str(path), cache_root=cache, context_size=8192)
        assert info == llm_metadata.ModelStorageInfo(None, None)


def test_file_disappearing_between_discovery_and_stat_is_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = tmp_path / "model.gguf"
    _write_gguf(model)
    original = llm_metadata._identity_unchanged

    def disappear(identity: object) -> bool:
        model.unlink()
        return original(identity)

    monkeypatch.setattr(llm_metadata, "_identity_unchanged", disappear)
    info = inspect_model(str(model), cache_root=tmp_path, context_size=8192)
    assert info == llm_metadata.ModelStorageInfo(None, None)


def test_file_becoming_inaccessible_during_read_is_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = tmp_path / "model.gguf"
    _write_gguf(model)

    def inaccessible(path: Path) -> dict[str, object]:
        raise PermissionError("denied")

    monkeypatch.setattr(llm_metadata, "_read_gguf_metadata", inaccessible)
    info = inspect_model(str(model), cache_root=tmp_path, context_size=8192)
    assert info == llm_metadata.ModelStorageInfo(None, None)


def test_temporary_read_error_is_not_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = tmp_path / "model.gguf"
    _write_gguf(model)
    original = llm_metadata._read_gguf_metadata
    reads = 0

    def temporarily_inaccessible(path: Path) -> dict[str, object]:
        nonlocal reads
        reads += 1
        if reads == 1:
            raise PermissionError("denied")
        return original(path)

    monkeypatch.setattr(llm_metadata, "_read_gguf_metadata", temporarily_inaccessible)
    failed = inspect_model(str(model), cache_root=tmp_path, context_size=8192)
    recovered = inspect_model(str(model), cache_root=tmp_path, context_size=8192)
    cached = inspect_model(str(model), cache_root=tmp_path, context_size=8192)

    assert failed == llm_metadata.ModelStorageInfo(None, None)
    assert recovered.size_bytes == model.stat().st_size
    assert recovered.vram_estimate_bytes is not None
    assert cached == recovered
    assert reads == 2


def test_unknown_estimate_is_not_cached_while_downloading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = tmp_path / "partial.gguf"
    model.write_bytes(b"GGUF")
    original = llm_metadata._read_gguf_metadata
    reads = 0

    def counted(path: Path) -> dict[str, object]:
        nonlocal reads
        reads += 1
        return original(path)

    monkeypatch.setattr(llm_metadata, "_read_gguf_metadata", counted)
    for _ in range(2):
        inspect_model(
            str(model),
            cache_root=tmp_path,
            context_size=8192,
            cache_unavailable=False,
        )
    assert reads == 2


def test_invalid_architecture_values_disable_estimate(tmp_path: Path) -> None:
    model = tmp_path / "invalid-architecture.gguf"
    _write_gguf(
        model,
        {
            "general.architecture": (8, "custom"),
            "custom.block_count": (4, 40),
            "custom.embedding_length": (4, 4097),
            "custom.attention.head_count": (4, 32),
            "custom.attention.head_count_kv": (4, 7),
        },
    )
    info = inspect_model(str(model), cache_root=tmp_path, context_size=8192)
    assert info.size_bytes == model.stat().st_size
    assert info.vram_estimate_bytes is None


def test_valid_size_without_vram_estimate_is_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = tmp_path / "unsupported-architecture.gguf"
    _write_gguf(model, {"general.architecture": (8, "unsupported")})
    original = llm_metadata._read_gguf_metadata
    reads = 0

    def counted(path: Path) -> dict[str, object]:
        nonlocal reads
        reads += 1
        return original(path)

    monkeypatch.setattr(llm_metadata, "_read_gguf_metadata", counted)
    first = inspect_model(str(model), cache_root=tmp_path, context_size=8192)
    second = inspect_model(str(model), cache_root=tmp_path, context_size=8192)

    assert first.size_bytes == model.stat().st_size
    assert first.vram_estimate_bytes is None
    assert second == first
    assert reads == 1


def test_formats_labels_without_false_precision() -> None:
    assert readable_model_name("ggml-org/Qwen3-14B-GGUF:Q4_K_M") == "Qwen3-14B"
    assert format_bytes(8 * 1024**3) == "8,0 Gio"
    assert format_bytes(None) == "Taille inconnue"


@pytest.mark.asyncio
async def test_snapshot_inspection_does_not_block_event_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Router:
        async def list_models(self) -> list[RouterModel]:
            return [RouterModel("model", "unloaded", None, None, None, False)]

    service = AdminLlmService(None, Router(), fallback_model="model")

    async def selected_model() -> str:
        return "model"

    def slow_inspection(*args: object, **kwargs: object) -> object:
        time.sleep(0.05)
        return llm_metadata.ModelStorageInfo(None, None)

    monkeypatch.setattr(service, "selected_model", selected_model)
    monkeypatch.setattr("app.llm_service.inspect_model", slow_inspection)
    completion_order = []

    async def snapshot() -> None:
        await service.snapshot()
        completion_order.append("snapshot")

    async def ticker() -> None:
        await asyncio.sleep(0.01)
        completion_order.append("ticker")

    await asyncio.gather(snapshot(), ticker())
    assert completion_order == ["ticker", "snapshot"]
