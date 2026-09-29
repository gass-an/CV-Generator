from io import BytesIO

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.shared import Cm, Pt


class DocxRenderingError(Exception):
    """Le contenu AsciiDoc ne peut pas être rendu en document DOCX."""


class DocxRenderer:
    """Convertit le sous-ensemble AsciiDoc produit par le LLM en fichier DOCX."""

    def render(self, asciidoc: str) -> bytes:
        """Produit un paquet DOCX valide en mémoire à partir du contenu AsciiDoc."""
        if not asciidoc.strip():
            raise DocxRenderingError("Le contenu AsciiDoc ne doit pas être vide")

        try:
            document = Document()
            self._configure_document(document)
            self._add_content(document, asciidoc)

            output = BytesIO()
            document.save(output)
            rendered = output.getvalue()

            # La réouverture détecte un paquet en mémoire incomplet ou invalide.
            Document(BytesIO(rendered))
            return rendered
        except DocxRenderingError:
            raise
        except Exception as error:
            raise DocxRenderingError(
                "Impossible de générer le document DOCX"
            ) from error

    def _configure_document(self, document: Document) -> None:
        section = document.sections[0]
        section.start_type = WD_SECTION.NEW_PAGE
        section.page_width = Cm(21)
        section.page_height = Cm(29.7)
        section.top_margin = Cm(2)
        section.bottom_margin = Cm(2)
        section.left_margin = Cm(2.2)
        section.right_margin = Cm(2.2)

        styles = document.styles

        normal = styles["Normal"]
        normal.font.name = "Arial"
        normal.font.size = Pt(10.5)
        normal.paragraph_format.space_after = Pt(6)
        normal.paragraph_format.line_spacing = 1.08

        title = styles["Title"]
        title.font.name = "Arial"
        title.font.size = Pt(24)
        title.font.bold = True
        title.paragraph_format.space_after = Pt(12)

        heading_1 = styles["Heading 1"]
        heading_1.font.name = "Arial"
        heading_1.font.size = Pt(15)
        heading_1.font.bold = True
        heading_1.paragraph_format.space_before = Pt(12)
        heading_1.paragraph_format.space_after = Pt(5)

        heading_2 = styles["Heading 2"]
        heading_2.font.name = "Arial"
        heading_2.font.size = Pt(11.5)
        heading_2.font.bold = True
        heading_2.paragraph_format.space_before = Pt(8)
        heading_2.paragraph_format.space_after = Pt(3)

        list_bullet = styles["List Bullet"]
        list_bullet.font.name = "Arial"
        list_bullet.font.size = Pt(10.5)
        list_bullet.paragraph_format.space_after = Pt(3)

    def _add_content(self, document: Document, asciidoc: str) -> None:
        for raw_line in asciidoc.splitlines():
            line = raw_line.rstrip()
            if not line.strip():
                continue

            if line.startswith("=== "):
                document.add_paragraph(line[4:].strip(), style="Heading 2")
            elif line.startswith("== "):
                document.add_paragraph(line[3:].strip(), style="Heading 1")
            elif line.startswith("= "):
                paragraph = document.add_paragraph(line[2:].strip(), style="Title")
                paragraph.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
            elif line.startswith("* "):
                document.add_paragraph(line[2:].strip(), style="List Bullet")
            else:
                document.add_paragraph(line.strip(), style="Normal")
