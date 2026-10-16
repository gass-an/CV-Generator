import re

from app.asciidoc import DELIMITED_BLOCK, normalize_asciidoc

HEADING = re.compile(r"^(?P<markers>={1,6})[ \t]+(?P<text>.+)$")
UNORDERED_ITEM = re.compile(r"^(?P<markers>\*+)[ \t]+(?P<text>.+)$")
ORDERED_ITEM = re.compile(r"^(?P<markers>\.+)[ \t]+(?P<text>.+)$")
INLINE_STYLE = re.compile(
    r"(?<![\\\w])(?P<marker>[*_])(?=\S)(?P<text>.+?)(?<=\S)(?P=marker)(?!\w)"
)
LINK = re.compile(r"(?P<url>https?://[^\s\[]+)\[(?P<label>[^]\n]+)]")
SOURCE_ATTRIBUTE = re.compile(r"^\[source(?:,(?P<language>[\w+-]+))?]$")
BACKTICK_SEQUENCE = re.compile(r"`+")


class MarkdownRenderingError(Exception):
    """Le contenu AsciiDoc ne peut pas être converti en Markdown."""


class MarkdownRenderer:
    """Convertit le sous-ensemble AsciiDoc produit par les prompts du service."""

    def render(self, asciidoc: str) -> str:
        if not asciidoc.strip():
            raise MarkdownRenderingError("Le contenu AsciiDoc ne doit pas être vide")

        try:
            output: list[str] = []
            block_delimiter: str | None = None
            block_language = ""
            block_lines: list[str] = []
            pending_source_attribute: tuple[str, str] | None = None
            for raw_line in normalize_asciidoc(asciidoc).splitlines():
                stripped = raw_line.strip()
                delimiter = DELIMITED_BLOCK.fullmatch(stripped)
                if block_delimiter is not None:
                    if stripped == block_delimiter:
                        output.extend(
                            self._render_block(
                                block_delimiter, block_lines, block_language
                            )
                        )
                        block_delimiter = None
                        block_language = ""
                        block_lines = []
                    else:
                        block_lines.append(raw_line)
                    continue
                if source_attribute := SOURCE_ATTRIBUTE.fullmatch(stripped):
                    pending_source_attribute = (
                        raw_line,
                        source_attribute.group("language") or "",
                    )
                    continue
                if delimiter is not None:
                    block_delimiter = stripped
                    if pending_source_attribute is not None and stripped != "----":
                        output.append(pending_source_attribute[0])
                    block_language = (
                        pending_source_attribute[1]
                        if pending_source_attribute is not None
                        else ""
                    )
                    pending_source_attribute = None
                    continue

                if pending_source_attribute is not None:
                    output.append(pending_source_attribute[0])
                    pending_source_attribute = None

                if heading := HEADING.fullmatch(raw_line.rstrip()):
                    output.append(
                        f"{'#' * len(heading.group('markers'))} "
                        f"{self._inline(heading.group('text'))}"
                    )
                elif item := UNORDERED_ITEM.fullmatch(raw_line.rstrip()):
                    level = len(item.group("markers"))
                    output.append(
                        f"{'    ' * (level - 1)}- {self._inline(item.group('text'))}"
                    )
                elif item := ORDERED_ITEM.fullmatch(raw_line.rstrip()):
                    level = len(item.group("markers"))
                    output.append(
                        f"{'    ' * (level - 1)}1. {self._inline(item.group('text'))}"
                    )
                else:
                    output.append(self._inline(raw_line.rstrip()))

            if block_delimiter is not None:
                output.extend(
                    self._render_block(block_delimiter, block_lines, block_language)
                )
            elif pending_source_attribute is not None:
                output.append(pending_source_attribute[0])
            return "\n".join(output).strip()
        except MarkdownRenderingError:
            raise
        except Exception as error:
            raise MarkdownRenderingError(
                "Impossible de convertir le document en Markdown"
            ) from error

    @staticmethod
    def _inline(text: str) -> str:
        linked = LINK.sub(r"[\g<label>](\g<url>)", text)

        def replace_style(match: re.Match[str]) -> str:
            marker = "**" if match.group("marker") == "*" else "_"
            return f"{marker}{match.group('text')}{marker}"

        return INLINE_STYLE.sub(replace_style, linked)

    @staticmethod
    def _render_block(delimiter: str, lines: list[str], language: str) -> list[str]:
        if delimiter == "____":
            return [">", *(f"> {line}" if line else ">" for line in lines), ">"]

        longest_sequence = max(
            (
                len(match.group())
                for line in lines
                for match in BACKTICK_SEQUENCE.finditer(line)
            ),
            default=0,
        )
        fence = "`" * max(3, longest_sequence + 1)
        return [f"{fence}{language}", *lines, fence]
