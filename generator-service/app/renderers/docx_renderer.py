from io import BytesIO

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.shared import Cm, Pt


class DocxRenderingError(Exception):
    """Raised when AsciiDoc content cannot be rendered as a DOCX document."""


class DocxRenderer:
    def render(self, asciidoc: str) -> bytes:
        if not asciidoc.strip():
            raise DocxRenderingError("AsciiDoc content must not be empty")

        try:
            document = Document()
            self._configure_document(document)
            self._add_content(document, asciidoc)

            output = BytesIO()
            document.save(output)
            rendered = output.getvalue()

            # Reopening the in-memory package catches incomplete or invalid output.
            Document(BytesIO(rendered))
            return rendered
        except DocxRenderingError:
            raise
        except Exception as error:
            raise DocxRenderingError("Unable to render the DOCX document") from error

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
