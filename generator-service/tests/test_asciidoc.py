import pytest
from app.asciidoc import normalize_asciidoc


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("Un **mot important** ici.", "Un *mot important* ici."),
        ("Un *mot important* ici.", "Un *mot important* ici."),
        ("- Premier\n- Deuxième", "* Premier\n* Deuxième"),
        ("* Premier\n** Sous-élément", "* Premier\n** Sous-élément"),
        ("- Premier\n  - Sous\n    - Profond", "* Premier\n** Sous\n*** Profond"),
        (
            "- **Compétence :** description\n  - **Preuve :** fait",
            "* *Compétence :* description\n** *Preuve :* fait",
        ),
        ("# Titre\n\n## Section\n\nParagraphe", "= Titre\n\n== Section\n\nParagraphe"),
        ("Texte déjà valide.\n\n* Élément", "Texte déjà valide.\n\n* Élément"),
        ("Calcul : 2 * 3 et motif ** isolé", "Calcul : 2 * 3 et motif ** isolé"),
        (r"Motif \**littéral** conservé", r"Motif \**littéral** conservé"),
        ("***important***", "***important***"),
        ("Texte ***gras et italique*** ambigu", "Texte ***gras et italique*** ambigu"),
        ("****séquence littérale****", "****séquence littérale****"),
        ("1. Première\n2. Deuxième", ". Première\n. Deuxième"),
        ("1. Première\n  1. Sous-étape", ". Première\n.. Sous-étape"),
        (". Déjà AsciiDoc\n.. Sous-étape", ". Déjà AsciiDoc\n.. Sous-étape"),
        ("Version 2. publiée", "Version 2. publiée"),
        ("2024. Bilan annuel", "2024. Bilan annuel"),
    ],
)
def test_normalize_asciidoc(source: str, expected: str) -> None:
    assert normalize_asciidoc(source) == expected


def test_normalization_preserves_delimited_block_verbatim() -> None:
    source = """= Exemple

....
**texte littéral**
- commande
# pas un titre
....

- Élément réel  
"""

    normalized = normalize_asciidoc(source)

    assert "....\n**texte littéral**\n- commande\n# pas un titre\n...." in normalized
    assert normalized.endswith("* Élément réel")


def test_normalization_preserves_trailing_spaces_inside_delimited_block() -> None:
    source = (
        "= Exemple\n\n....\nligne avec deux espaces  \n  ligne indentée  \n\n....\n"
    )

    normalized = normalize_asciidoc(source)

    assert "....\nligne avec deux espaces  \n  ligne indentée  \n\n...." in normalized


def test_normalization_is_idempotent() -> None:
    source = "# Titre  \n\n- **Élément**\n  - Sous-élément"
    once = normalize_asciidoc(source)
    assert normalize_asciidoc(once) == once


@pytest.mark.parametrize(
    "source",
    [
        "***important***",
        "Avant ***gras et italique*** après",
        "****séquence****",
        "- **gras**\n  - ***ambigu***",
        "1. **Première**\n  1. ***Sous-étape ambiguë***",
    ],
)
def test_normalization_is_idempotent_for_asterisk_sequences(source: str) -> None:
    once = normalize_asciidoc(source)
    assert normalize_asciidoc(once) == once


def test_normalization_keeps_text_while_changing_only_markers() -> None:
    source = "## Analyse\n- **Rédaction de procédures :** expérience pertinente."
    normalized = normalize_asciidoc(source)

    for text in ("Analyse", "Rédaction de procédures :", "expérience pertinente."):
        assert text in normalized
