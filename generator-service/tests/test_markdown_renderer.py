import pytest
from app.renderers import MarkdownRenderer, MarkdownRenderingError
from markdown_it import MarkdownIt


def test_render_converts_supported_asciidoc_structure() -> None:
    source = """= CV de Maëva

== Expérience

Un paragraphe avec *du gras*, _de l'italique_ et https://example.nc[un lien].

* Élément
** Sous-élément & caractères spéciaux
. Première étape
.. Sous-étape
"""

    assert (
        MarkdownRenderer().render(source)
        == """# CV de Maëva

## Expérience

Un paragraphe avec **du gras**, _de l'italique_ et [un lien](https://example.nc).

- Élément
    - Sous-élément & caractères spéciaux
1. Première étape
    1. Sous-étape"""
    )


def test_render_produces_real_commonmark_nested_and_mixed_lists() -> None:
    source = """. Parent numéroté
.. Enfant numéroté
*** Petit-enfant à puce
* Parent à puce
** Enfant à puce
... Petit-enfant numéroté"""

    rendered = MarkdownRenderer().render(source)
    html = MarkdownIt("commonmark").render(rendered)

    assert "<ol>\n<li>Parent numéroté\n<ol>" in html
    assert "<li>Enfant numéroté\n<ul>" in html
    assert "<ul>\n<li>Parent à puce\n<ul>" in html
    assert "<li>Enfant à puce\n<ol>" in html


def test_render_reuses_asciidoc_normalization_without_changing_source() -> None:
    source = """# Titre accidentel

- Élément Markdown
  - Sous-élément Markdown

Un mot **important**."""

    rendered = MarkdownRenderer().render(source)

    assert source.startswith("# Titre accidentel")
    assert (
        rendered
        == """# Titre accidentel

- Élément Markdown
    - Sous-élément Markdown

Un mot **important**."""
    )


def test_render_preserves_unknown_delimited_block_content() -> None:
    source = """== Exemple

----
* ceci reste littéral
contenu inconnu
----"""

    assert (
        MarkdownRenderer().render(source)
        == """## Exemple

```
* ceci reste littéral
contenu inconnu
```"""
    )


def test_render_preserves_source_and_quote_block_semantics() -> None:
    source = """[source,python]
----
print("bonjour")
----

____
Une citation.
____"""

    tokens = MarkdownIt("commonmark").parse(MarkdownRenderer().render(source))

    fence = next(token for token in tokens if token.type == "fence")
    assert fence.info == "python"
    assert fence.content == 'print("bonjour")\n'
    assert [token.type for token in tokens].count("blockquote_open") == 1


@pytest.mark.parametrize("backtick_count", [3, 4, 7])
def test_render_uses_safe_fence_for_backticks_inside_source_block(
    backtick_count: int,
) -> None:
    embedded_fence = "`" * backtick_count
    content_lines = [
        "    ligne indentée",
        f'{embedded_fence}python title="exemple"',
        'print("préservé")',
        embedded_fence,
    ]
    source = "\n".join(["[source,python]", "----", *content_lines, "----"])

    rendered = MarkdownRenderer().render(source)
    tokens = MarkdownIt("commonmark").parse(rendered)
    fences = [token for token in tokens if token.type == "fence"]

    assert len(fences) == 1
    assert fences[0].info == "python"
    assert fences[0].content == "\n".join(content_lines) + "\n"
    opening_fence, *_, closing_fence = rendered.splitlines()
    assert opening_fence == f"{'`' * (backtick_count + 1)}python"
    assert closing_fence == "`" * (backtick_count + 1)


@pytest.mark.parametrize("source", ["", "  \n\t"])
def test_render_rejects_empty_content(source: str) -> None:
    with pytest.raises(MarkdownRenderingError):
        MarkdownRenderer().render(source)
