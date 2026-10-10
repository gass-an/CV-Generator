import asyncio
import os
import signal
import tempfile
from collections.abc import Awaitable, Callable
from contextlib import suppress
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends

from app.core.config import get_settings

PDF_HEADER = b"%PDF-"
PDF_EOF = b"%%EOF"


class PdfConversionError(Exception):
    """La conversion DOCX vers PDF a échoué sans détail exposable."""


class PdfConversionTimeoutError(PdfConversionError):
    """LibreOffice n'a pas terminé dans le délai autorisé."""


ProcessRunner = Callable[[list[str]], Awaitable[None]]


class LibreOfficePdfConverter:
    """Convertit un DOCX en PDF via un processus LibreOffice isolé."""

    def __init__(
        self,
        *,
        executable: str,
        timeout_seconds: float,
        max_concurrent: int,
        process_runner: ProcessRunner | None = None,
    ) -> None:
        self._executable = executable
        self._timeout_seconds = timeout_seconds
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._process_runner = process_runner or self._run_process

    async def convert(self, docx_content: bytes) -> bytes:
        """Convertit hors transaction et nettoie toujours les fichiers temporaires."""
        if not docx_content:
            raise PdfConversionError("Le document DOCX est vide")

        async with self._semaphore:
            with tempfile.TemporaryDirectory(prefix="cv-generator-pdf-") as temp_name:
                temp_dir = Path(temp_name)
                input_path = temp_dir / "document.docx"
                output_path = temp_dir / "document.pdf"
                profile_path = temp_dir / "libreoffice-profile"
                # Écriture locale bornée avant le sous-processus asynchrone.
                input_path.write_bytes(docx_content)  # noqa: ASYNC240
                command = [
                    self._executable,
                    f"-env:UserInstallation={profile_path.as_uri()}",
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(temp_dir),
                    str(input_path),
                ]
                try:
                    await asyncio.wait_for(
                        self._process_runner(command),
                        timeout=self._timeout_seconds,
                    )
                except TimeoutError as error:
                    raise PdfConversionTimeoutError(
                        "La conversion PDF a dépassé le délai autorisé"
                    ) from error
                except PdfConversionError:
                    raise
                except Exception as error:
                    raise PdfConversionError("La conversion PDF a échoué") from error

                try:
                    # Lecture locale bornée après la fin de LibreOffice.
                    pdf_content = output_path.read_bytes()  # noqa: ASYNC240
                except OSError as error:
                    raise PdfConversionError(
                        "Le fichier PDF est indisponible"
                    ) from error
                if not self._is_valid_pdf(pdf_content):
                    raise PdfConversionError("Le fichier PDF produit est invalide")
                return pdf_content

    async def _run_process(self, command: list[str]) -> None:
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as error:
            raise PdfConversionError("LibreOffice est indisponible") from error
        try:
            await process.wait()
        except asyncio.CancelledError:
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            await process.wait()
            raise
        if process.returncode != 0:
            raise PdfConversionError("LibreOffice a refusé la conversion")

    @staticmethod
    def _is_valid_pdf(content: bytes) -> bool:
        return content.startswith(PDF_HEADER) and PDF_EOF in content[-1024:]


@lru_cache
def _build_pdf_converter() -> LibreOfficePdfConverter:
    settings = get_settings()
    return LibreOfficePdfConverter(
        executable=settings.libreoffice_executable,
        timeout_seconds=settings.pdf_conversion_timeout_seconds,
        max_concurrent=settings.pdf_conversion_max_concurrent,
    )


async def get_pdf_converter() -> LibreOfficePdfConverter:
    """Expose le convertisseur partagé sans passage par le threadpool FastAPI."""
    return _build_pdf_converter()


PdfConverter = Annotated[LibreOfficePdfConverter, Depends(get_pdf_converter)]
