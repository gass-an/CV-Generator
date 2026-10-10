import asyncio
import os
import shutil
from pathlib import Path

import pytest
from app.renderers import DocxRenderer
from app.services.pdf_conversion_service import (
    LibreOfficePdfConverter,
    PdfConversionError,
    PdfConversionTimeoutError,
)

VALID_PDF = b"%PDF-1.4\n1 0 obj\nendobj\n%%EOF"


def output_path_from(command: list[str]) -> Path:
    return Path(command[command.index("--outdir") + 1]) / "document.pdf"


@pytest.mark.asyncio
async def test_converter_returns_pdf_and_cleans_isolated_directory() -> None:
    temporary_directory: Path | None = None

    async def successful_runner(command: list[str]) -> None:
        nonlocal temporary_directory
        temporary_directory = Path(command[command.index("--outdir") + 1])
        assert Path(command[-1]).read_bytes() == b"docx-content"  # noqa: ASYNC240
        assert command[0] == "libreoffice-test"
        assert any(
            argument.startswith("-env:UserInstallation=file://") for argument in command
        )
        output_path_from(command).write_bytes(VALID_PDF)  # noqa: ASYNC240

    converter = LibreOfficePdfConverter(
        executable="libreoffice-test",
        timeout_seconds=1,
        max_concurrent=1,
        process_runner=successful_runner,
    )

    assert await converter.convert(b"docx-content") == VALID_PDF
    assert temporary_directory is not None
    assert not temporary_directory.exists()  # noqa: ASYNC240


@pytest.mark.asyncio
async def test_converter_timeout_cleans_temporary_directory() -> None:
    temporary_directory: Path | None = None

    async def slow_runner(command: list[str]) -> None:
        nonlocal temporary_directory
        temporary_directory = Path(command[command.index("--outdir") + 1])
        await asyncio.sleep(1)

    converter = LibreOfficePdfConverter(
        executable="libreoffice",
        timeout_seconds=0.01,
        max_concurrent=1,
        process_runner=slow_runner,
    )

    with pytest.raises(PdfConversionTimeoutError):
        await converter.convert(b"docx-content")
    assert temporary_directory is not None
    assert not temporary_directory.exists()  # noqa: ASYNC240


@pytest.mark.asyncio
@pytest.mark.parametrize("pdf_content", [None, b"", b"not-a-pdf", b"%PDF-1.4"])
async def test_converter_rejects_missing_or_invalid_output(
    pdf_content: bytes | None,
) -> None:
    temporary_directory: Path | None = None

    async def invalid_runner(command: list[str]) -> None:
        nonlocal temporary_directory
        temporary_directory = Path(command[command.index("--outdir") + 1])
        if pdf_content is not None:
            output_path_from(command).write_bytes(pdf_content)  # noqa: ASYNC240

    converter = LibreOfficePdfConverter(
        executable="libreoffice",
        timeout_seconds=1,
        max_concurrent=1,
        process_runner=invalid_runner,
    )

    with pytest.raises(PdfConversionError):
        await converter.convert(b"docx-content")
    assert temporary_directory is not None
    assert not temporary_directory.exists()  # noqa: ASYNC240


@pytest.mark.asyncio
async def test_converter_limits_concurrent_processes() -> None:
    active = 0
    maximum_active = 0

    async def recording_runner(command: list[str]) -> None:
        nonlocal active, maximum_active
        active += 1
        maximum_active = max(maximum_active, active)
        await asyncio.sleep(0.01)
        output_path_from(command).write_bytes(VALID_PDF)  # noqa: ASYNC240
        active -= 1

    converter = LibreOfficePdfConverter(
        executable="libreoffice",
        timeout_seconds=1,
        max_concurrent=1,
        process_runner=recording_runner,
    )

    await asyncio.gather(*(converter.convert(b"docx") for _ in range(3)))
    assert maximum_active == 1


@pytest.mark.asyncio
async def test_real_libreoffice_conversion_when_available() -> None:
    if os.getenv("RUN_LIBREOFFICE_INTEGRATION") != "1":
        pytest.skip("RUN_LIBREOFFICE_INTEGRATION=1 n'est pas défini")
    executable = shutil.which("libreoffice")
    if executable is None:
        pytest.skip("LibreOffice n'est pas installé")
    docx_content = DocxRenderer().render("= Smoke test PDF\n\nContenu de test.")
    converter = LibreOfficePdfConverter(
        executable=executable,
        timeout_seconds=30,
        max_concurrent=1,
    )

    pdf_content = await converter.convert(docx_content)

    assert pdf_content.startswith(b"%PDF-")
    assert b"%%EOF" in pdf_content[-1024:]
