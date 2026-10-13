import re

from app.models.document_job import DocumentType
from app.processors.document_processor import (
    AvpLlmDocumentProcessor,
    DocumentJobData,
    GeneratedDocument,
)

SUBJECT_LINE = re.compile(
    r"^(?P<label>[ \t]*(?:\*Objet\s*:\*|Objet\s*:)[ \t]*)(?P<subject>\S.*?)[ \t]*$",
    flags=re.IGNORECASE | re.MULTILINE,
)
CANDIDATURE_TO_POSITION = re.compile(
    r"^Candidature\s+(?:au|pour le)\s+poste\s+(?:de\s+|d['’])(?P<title>.+)$",
    flags=re.IGNORECASE,
)
SALUTATION_LINE = re.compile(
    r"^[ \t]*(?:Madame|Monsieur)(?:[ \t]*,|[ \t]+|$).*$",
    flags=re.IGNORECASE | re.MULTILINE,
)
DOCUMENT_TITLE_LINE = re.compile(r"^=[ \t]+.+$", flags=re.MULTILINE)


def _insert_asciidoc_block(content: str, position: int, block: str) -> str:
    before = content[:position]
    after = content[position:]
    before_separator = "\n\n"
    if not before or before.endswith("\n\n"):
        before_separator = ""
    elif before.endswith("\n"):
        before_separator = "\n"

    after_separator = "\n\n"
    if not after or after.startswith("\n\n"):
        after_separator = ""
    elif after.startswith("\n"):
        after_separator = "\n"
    return f"{before}{before_separator}{block}{after_separator}{after}"


def include_offer_reference_in_subject(content: str, reference: str) -> str:
    """Ajoute la référence officielle à l'objet existant sans la dupliquer."""
    normalized_reference = reference.strip()
    if not normalized_reference:
        return content

    subject_line = SUBJECT_LINE.search(content)
    if subject_line is None:
        fallback_subject = f"Objet : Candidature à l'offre n° {normalized_reference}"
        salutation = SALUTATION_LINE.search(content)
        if salutation is not None:
            return _insert_asciidoc_block(
                content,
                salutation.start(),
                fallback_subject,
            )
        title = DOCUMENT_TITLE_LINE.search(content)
        position = title.end() if title is not None else 0
        return _insert_asciidoc_block(content, position, fallback_subject)

    if normalized_reference.casefold() in subject_line.group("subject").casefold():
        return content

    subject = subject_line.group("subject")
    candidature = CANDIDATURE_TO_POSITION.fullmatch(subject)
    if candidature is not None:
        subject = (
            f"Candidature à l'offre n° {normalized_reference}"
            f" – {candidature.group('title')}"
        )
    else:
        subject = f"{subject} – offre n° {normalized_reference}"
    enriched_subject = f"{subject_line.group('label')}{subject}"
    before_subject = content[: subject_line.start()]
    after_subject = content[subject_line.end() :]
    return f"{before_subject}{enriched_subject}{after_subject}"


class CoverLetterDocumentProcessor(AvpLlmDocumentProcessor):
    """Génère une lettre de motivation AsciiDoc adaptée à un AVP exact."""

    document_type = DocumentType.COVER_LETTER

    async def process(self, job: DocumentJobData) -> GeneratedDocument:
        document = await super().process(job)
        return GeneratedDocument(
            content=include_offer_reference_in_subject(
                document.content,
                job.avp_number,
            ),
            format=document.format,
        )
