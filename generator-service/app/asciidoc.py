import re

MARKDOWN_HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)\s*$")
MARKDOWN_BULLET = re.compile(r"^(?P<indent>[ \t]*)-[ \t]+(?P<text>\S.*)$")
MARKDOWN_NUMBERED_ITEM = re.compile(
    r"^(?P<indent>[ \t]*)(?P<number>[1-9]\d{0,2})\.[ \t]+(?P<text>\S.*)$"
)
MARKDOWN_BOLD = re.compile(
    r"(?<![\\*])\*\*(?=[^\s*])(?P<text>.+?)(?<=[^\s*])\*\*(?!\*)"
)
DELIMITED_BLOCK = re.compile(r"^(?P<delimiter>[-.+_=*/])(?P=delimiter){3,}$")


def normalize_asciidoc(content: str) -> str:
    """Corrige prudemment les erreurs Markdown courantes dans de l'AsciiDoc.

    Les transformations sont limitées aux constructions non ambiguës et ne sont
    jamais appliquées à l'intérieur des blocs délimités AsciiDoc.
    """
    normalized_lines: list[str] = []
    open_delimiter: str | None = None

    for raw_line in content.splitlines():
        stripped_line = raw_line.strip()
        delimiter = DELIMITED_BLOCK.fullmatch(stripped_line)
        if open_delimiter is not None:
            normalized_lines.append(raw_line)
            if stripped_line == open_delimiter:
                open_delimiter = None
            continue
        if delimiter is not None:
            open_delimiter = stripped_line
            normalized_lines.append(raw_line)
            continue

        line = raw_line.rstrip()
        heading = MARKDOWN_HEADING.fullmatch(line)
        if heading is not None:
            level = len(heading.group(1))
            line = f"{'=' * level} {heading.group(2)}"
        else:
            bullet = MARKDOWN_BULLET.fullmatch(line)
            if bullet is not None:
                level = _markdown_list_level(bullet.group("indent"))
                line = f"{'*' * level} {bullet.group('text')}"
            else:
                numbered_item = MARKDOWN_NUMBERED_ITEM.fullmatch(line)
                if numbered_item is not None:
                    level = _markdown_list_level(numbered_item.group("indent"))
                    line = f"{'.' * level} {numbered_item.group('text')}"

        normalized_lines.append(MARKDOWN_BOLD.sub(r"*\g<text>*", line))

    return "\n".join(normalized_lines).strip()


def _markdown_list_level(indent: str) -> int:
    """Convertit une indentation Markdown en niveau AsciiDoc stable."""
    columns = 0
    for character in indent:
        columns += 4 if character == "\t" else 1
    if columns == 0:
        return 1
    return 1 + ((columns - 1) // 2) + 1
