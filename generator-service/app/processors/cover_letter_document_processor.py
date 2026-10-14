import re

from app.models.document_job import DocumentType
from app.processors.document_processor import (
    AvpLlmDocumentProcessor,
    DocumentJobData,
    GeneratedDocument,
)

SUBJECT_LINE = re.compile(
    r"^(?P<indent>[ \t]*)(?:"
    r"(?P<label_marker>\*{1,2})Objet[ \t]*:[ \t]*(?P=label_marker)"
    r"[ \t]*(?P<label_subject>[^\r\n]*?)"
    r"|(?P<whole_marker>\*{1,2})Objet[ \t]*:[ \t]*"
    r"(?P<whole_subject>[^\r\n]*?)(?P=whole_marker)"
    r"|Objet[ \t]*:[ \t]*(?P<plain_subject>[^\r\n]*?)"
    r")[ \t]*$",
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

    subject = next(
        subject_line.group(name)
        for name in ("whole_subject", "label_subject", "plain_subject")
        if subject_line.group(name) is not None
    ).rstrip()
    if normalized_reference.casefold() in subject.casefold():
        return content

    candidature = CANDIDATURE_TO_POSITION.fullmatch(subject)
    if not subject:
        subject = f"Candidature à l'offre n° {normalized_reference}"
    elif candidature is not None:
        subject = (
            f"Candidature à l'offre n° {normalized_reference}"
            f" – {candidature.group('title')}"
        )
    else:
        subject = f"{subject} – offre n° {normalized_reference}"
    indent = subject_line.group("indent")
    whole_marker = subject_line.group("whole_marker")
    label_marker = subject_line.group("label_marker")
    if whole_marker is not None:
        enriched_subject = f"{indent}{whole_marker}Objet : {subject}{whole_marker}"
    elif label_marker is not None:
        enriched_subject = f"{indent}{label_marker}Objet :{label_marker} {subject}"
    else:
        enriched_subject = f"{indent}Objet : {subject}"
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
