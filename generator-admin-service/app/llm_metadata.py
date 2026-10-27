"""Inspection locale bornée et estimation prudente des modèles GGUF."""

from __future__ import annotations

import logging
import re
import struct
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

logger = logging.getLogger(__name__)

MAX_GGUF_KEY_BYTES = 4 * 1024
MAX_GGUF_STRING_BYTES = 1024 * 1024
MAX_GGUF_ARRAY_ITEMS = 1_000_000
MAX_GGUF_KV_COUNT = 100_000
MAX_GGUF_METADATA_BYTES = 128 * 1024 * 1024
MAX_GGUF_NESTING = 1
MAX_CACHE_ENTRIES = 128
LOG_THROTTLE_SECONDS = 300

GGUF_TYPES = {
    0: "B",
    1: "b",
    2: "H",
    3: "h",
    4: "I",
    5: "i",
    6: "f",
    7: "?",
    10: "Q",
    11: "q",
    12: "d",
}


@dataclass(frozen=True, slots=True)
class ModelStorageInfo:
    size_bytes: int | None
    vram_estimate_bytes: int | None


@dataclass(frozen=True, slots=True)
class _FileIdentity:
    path: Path
    device: int
    inode: int
    size: int
    modified_ns: int


class _BoundedReader:
    def __init__(self, stream: BinaryIO, file_size: int) -> None:
        self.stream = stream
        self.file_size = file_size
        self.inspected = 0

    def read(self, size: int) -> bytes:
        self._reserve(size)
        value = self.stream.read(size)
        if len(value) != size:
            raise EOFError("métadonnées GGUF incomplètes")
        self.inspected += size
        return value

    def skip(self, size: int) -> None:
        self._reserve(size)
        position = self.stream.tell()
        if position + size > self.file_size:
            raise EOFError("métadonnées GGUF incomplètes")
        self.stream.seek(size, 1)
        self.inspected += size

    def _reserve(self, size: int) -> None:
        if size < 0 or self.inspected + size > MAX_GGUF_METADATA_BYTES:
            raise ValueError("volume de métadonnées GGUF excessif")


class ModelMetadataCache:
    """Petit cache mémoire LRU invalidé par l'identité de tous les shards."""

    def __init__(self, max_entries: int = MAX_CACHE_ENTRIES) -> None:
        self._max_entries = max_entries
        self._entries: OrderedDict[
            tuple[tuple[_FileIdentity, ...], int, int], ModelStorageInfo
        ] = OrderedDict()
        self._lock = threading.Lock()

    def inspect(
        self,
        path_value: str | None,
        *,
        cache_root: Path,
        context_size: int,
        gpu_layers: int = 99,
        cache_unavailable: bool = True,
    ) -> ModelStorageInfo:
        try:
            identities = _model_file_identities(path_value, cache_root)
        except (OSError, ValueError) as error:
            _log_inspection_problem(error)
            return ModelStorageInfo(None, None)
        if not identities:
            return ModelStorageInfo(None, None)

        key = (identities, context_size, gpu_layers)
        with self._lock:
            cached = self._entries.get(key)
            if cached is not None:
                self._entries.move_to_end(key)
                return cached

        result = _inspect_identities(identities, context_size, gpu_layers)
        if result.size_bytes is not None and (
            result.vram_estimate_bytes is not None or cache_unavailable
        ):
            with self._lock:
                self._entries[key] = result
                self._entries.move_to_end(key)
                while len(self._entries) > self._max_entries:
                    self._entries.popitem(last=False)
        return result

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


_metadata_cache = ModelMetadataCache()
_log_lock = threading.Lock()
_last_log_by_error: dict[type[BaseException], float] = {}


def format_bytes(value: int | None) -> str:
    if value is None or value < 0:
        return "Taille inconnue"
    unit = "Mio" if value < 1024**3 else "Gio"
    divisor = 1024**2 if unit == "Mio" else 1024**3
    amount = value / divisor
    return (
        f"{amount:.0f} {unit}"
        if unit == "Mio"
        else f"{amount:.1f} {unit}".replace(".", ",")
    )


def readable_model_name(model_id: str) -> str:
    name = model_id.split("/", 1)[-1].split(":", 1)[0]
    return re.sub(r"-GGUF$", "", name, flags=re.IGNORECASE)


def inspect_model(
    path_value: str | None,
    *,
    cache_root: Path,
    context_size: int,
    gpu_layers: int = 99,
    cache_unavailable: bool = True,
) -> ModelStorageInfo:
    return _metadata_cache.inspect(
        path_value,
        cache_root=cache_root,
        context_size=context_size,
        gpu_layers=gpu_layers,
        cache_unavailable=cache_unavailable,
    )


def _model_file_identities(
    path_value: str | None, cache_root: Path
) -> tuple[_FileIdentity, ...]:
    paths = _model_files(path_value, cache_root)
    if not paths:
        return ()
    identities = []
    for path in paths:
        stat = path.stat()
        if not path.is_file():
            return ()
        identities.append(
            _FileIdentity(
                path=path,
                device=stat.st_dev,
                inode=stat.st_ino,
                size=stat.st_size,
                modified_ns=stat.st_mtime_ns,
            )
        )
    return tuple(identities)


def _model_files(path_value: str | None, cache_root: Path) -> list[Path]:
    if not path_value:
        return []
    root = cache_root.resolve(strict=True)
    resolved = Path(path_value).resolve(strict=True)
    resolved.relative_to(root)
    if not resolved.is_file() or resolved.suffix.lower() != ".gguf":
        return []
    match = re.fullmatch(r"(.+)-(\d{5})-of-(\d{5})\.gguf", resolved.name, re.I)
    if not match:
        return [resolved]
    count = int(match.group(3))
    if count < 1 or count > 10_000:
        return []
    shards = []
    for index in range(1, count + 1):
        shard = (
            resolved.parent / f"{match.group(1)}-{index:05d}-of-{count:05d}.gguf"
        ).resolve(strict=True)
        shard.relative_to(root)
        if not shard.is_file():
            return []
        shards.append(shard)
    return shards


def _inspect_identities(
    identities: tuple[_FileIdentity, ...], context_size: int, gpu_layers: int
) -> ModelStorageInfo:
    try:
        # Un second stat ferme la fenêtre entre découverte et lecture et évite
        # d'associer une estimation à un fichier remplacé pendant l'inspection.
        if any(not _identity_unchanged(identity) for identity in identities):
            return ModelStorageInfo(None, None)
        size = sum(identity.size for identity in identities)
        metadata = _read_gguf_metadata(identities[0].path)
        if any(not _identity_unchanged(identity) for identity in identities):
            return ModelStorageInfo(None, None)
        estimate = _estimate_vram(size, metadata, context_size, gpu_layers)
        return ModelStorageInfo(size, estimate)
    except (OSError, UnicodeError, ValueError, EOFError, struct.error) as error:
        _log_inspection_problem(error)
        return ModelStorageInfo(None, None)


def _identity_unchanged(identity: _FileIdentity) -> bool:
    stat = identity.path.stat()
    return (
        stat.st_dev,
        stat.st_ino,
        stat.st_size,
        stat.st_mtime_ns,
    ) == (identity.device, identity.inode, identity.size, identity.modified_ns)


def _log_inspection_problem(error: BaseException) -> None:
    now = time.monotonic()
    error_type = type(error)
    with _log_lock:
        previous = _last_log_by_error.get(error_type, 0)
        if now - previous < LOG_THROTTLE_SECONDS:
            return
        _last_log_by_error[error_type] = now
    logger.warning(
        "Inspection locale GGUF indisponible exception_type=%s",
        error_type.__name__,
    )


def _read_gguf_metadata(path: Path) -> dict[str, object]:
    with path.open("rb") as stream:
        reader = _BoundedReader(stream, path.stat().st_size)
        if reader.read(4) != b"GGUF":
            raise ValueError("en-tête GGUF invalide")
        version = struct.unpack("<I", reader.read(4))[0]
        if version not in {2, 3}:
            raise ValueError("version GGUF non prise en charge")
        _tensor_count, kv_count = struct.unpack("<QQ", reader.read(16))
        if kv_count > MAX_GGUF_KV_COUNT:
            raise ValueError("nombre de métadonnées GGUF excessif")
        values: dict[str, object] = {}
        for _ in range(kv_count):
            key = _read_string(reader, limit=MAX_GGUF_KEY_BYTES)
            value_type = struct.unpack("<I", reader.read(4))[0]
            wanted = key == "general.architecture" or key.endswith(
                (
                    ".block_count",
                    ".embedding_length",
                    ".attention.head_count",
                    ".attention.head_count_kv",
                )
            )
            value = _scalar(reader, value_type, keep=wanted, depth=0)
            if wanted:
                values[key] = value
        return values


def _read_string(
    reader: _BoundedReader, *, limit: int, keep: bool = True
) -> str | None:
    length = struct.unpack("<Q", reader.read(8))[0]
    if length > limit:
        raise ValueError("chaîne GGUF excessive")
    if not keep:
        reader.skip(length)
        return None
    return reader.read(length).decode("utf-8")


def _scalar(
    reader: _BoundedReader,
    value_type: int,
    *,
    keep: bool,
    depth: int,
) -> object:
    if value_type == 8:
        return _read_string(reader, limit=MAX_GGUF_STRING_BYTES, keep=keep)
    if value_type == 9:
        if depth >= MAX_GGUF_NESTING:
            raise ValueError("tableau GGUF imbriqué")
        element_type = struct.unpack("<I", reader.read(4))[0]
        length = struct.unpack("<Q", reader.read(8))[0]
        if length > MAX_GGUF_ARRAY_ITEMS:
            raise ValueError("tableau GGUF excessif")
        element_format = GGUF_TYPES.get(element_type)
        if element_format is not None:
            reader.skip(length * struct.calcsize(element_format))
            return None
        if element_type not in {8, 9}:
            raise ValueError("type GGUF inconnu")
        for _ in range(length):
            _scalar(reader, element_type, keep=False, depth=depth + 1)
        return None
    fmt = GGUF_TYPES.get(value_type)
    if fmt is None:
        raise ValueError("type GGUF inconnu")
    value = struct.unpack(f"<{fmt}", reader.read(struct.calcsize(fmt)))[0]
    return value if keep else None


def _estimate_vram(
    file_size: int,
    metadata: dict[str, object],
    context_size: int,
    gpu_layers: int,
) -> int | None:
    architecture = metadata.get("general.architecture")
    if not isinstance(architecture, str) or not architecture:
        return None

    def integer(suffix: str, *, maximum: int) -> int | None:
        value = metadata.get(f"{architecture}.{suffix}")
        return value if isinstance(value, int) and 0 < value <= maximum else None

    layers = integer("block_count", maximum=1000)
    embedding = integer("embedding_length", maximum=1_000_000)
    heads = integer("attention.head_count", maximum=100_000)
    kv_heads = integer("attention.head_count_kv", maximum=100_000) or heads
    if not all((layers, embedding, heads, kv_heads)):
        return None
    if embedding % heads or kv_heads > heads or heads % kv_heads:
        return None
    if context_size <= 0 or gpu_layers <= 0:
        return None

    offloaded_layers = min(gpu_layers, layers)
    # Approximation documentée : les poids GGUF sont répartis uniformément entre
    # blocs, avec deux blocs supplémentaires pour embeddings/sortie. Elle est
    # adaptée aux transformers denses/GQA usuels, sans prétendre mesurer CUDA.
    gpu_weight_ratio = (offloaded_layers + 2) / (layers + 2)
    gpu_weights = int(file_size * min(1.0, gpu_weight_ratio))
    # K et V sont supposés F16 (valeur llama.cpp par défaut), pour les seules
    # couches offloadées. Les architectures atypiques sont rejetées ci-dessus.
    kv_width = embedding * kv_heads // heads
    kv_cache = context_size * offloaded_layers * kv_width * 2 * 2
    # Les graphes et allocations CUDA varient selon le backend et le batch.
    compute_and_cuda = max(512 * 1024**2, int(gpu_weights * 0.08))
    estimate = gpu_weights + kv_cache + compute_and_cuda
    return estimate if estimate > 0 else None
