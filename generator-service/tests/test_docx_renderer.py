from io import BytesIO

import pytest
from app.renderers import DocxRenderer, DocxRenderingError
from docx import Document

ASCIIDOC_CV = """= Camille Exemple

Email : camille@example.nc
Téléphone : +687 75 00 00

== Profil

Professionnelle organisée et attentive à la qualité.

== Compétences

* Rédaction de procédures : Documentation, Formalisation
* Analyse de processus : Amélioration continue, Organisation

== Expériences professionnelles

=== Assistante qualité — Entreprise Exemple

2023 - 2025

* Rédaction et mise à jour de procédures internes
* Analyse de processus existants

== Formation

=== Licence en Gestion — Université Exemple

2018 - 2021
"""


def test_render_creates_readable_docx_with_expected_content_and_styles() -> None:
    rendered = DocxRenderer().render(ASCIIDOC_CV)

    document = Document(BytesIO(rendered))
    paragraphs = {
        paragraph.text: paragraph.style.name for paragraph in document.paragraphs
    }

    assert paragraphs["Camille Exemple"] == "Title"
    assert paragraphs["Profil"] == "Heading 1"
    assert paragraphs["Compétences"] == "Heading 1"
    assert paragraphs["Expériences professionnelles"] == "Heading 1"
    assert paragraphs["Assistante qualité — Entreprise Exemple"] == "Heading 2"
    assert paragraphs["Formation"] == "Heading 1"
    assert paragraphs["Licence en Gestion — Université Exemple"] == "Heading 2"
    assert (
        paragraphs["Rédaction de procédures : Documentation, Formalisation"]
        == "List Bullet"
    )
    assert paragraphs["Analyse de processus existants"] == "List Bullet"


@pytest.mark.parametrize("asciidoc", ["", "   ", "\n\t\n"])
def test_render_rejects_empty_content(asciidoc: str) -> None:
    with pytest.raises(DocxRenderingError, match="must not be empty"):
        DocxRenderer().render(asciidoc)
