"""Leitor mínimo de HCL (Terraform) para as regras estruturadas (ADR-FINOPS-001).

Não avalia nada: reconhece blocos (`resource "tipo" "nome" { ... }`), atributos e o
conteúdo de mapas literais, com número de linha, para o motor saber se um bloco foi
tocado pelo PR. Escrito aqui, e não com uma biblioteca, para o lock de dependências
(com hash) não crescer por causa de uma regra.

O que ele entende: comentários (`#`, `//`, `/* */`), strings com interpolação
(`${...}`), heredoc, blocos aninhados e expressões em várias linhas. O que ele não faz:
resolver variáveis, módulos, `for_each`/`count` ou funções (além do `merge` que o motor
trata em structured.py). Onde não dá para saber, quem usa o leitor deve tratar como
desconhecido e não afirmar nada.
"""

import re
from dataclasses import dataclass, field

_IDENT = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.\-]*")
_HEREDOC = re.compile(r"<<-?([A-Za-z_][A-Za-z0-9_]*)[ \t]*\r?\n")


@dataclass(frozen=True)
class Token:
    kind: str  # "id" | "str" | "p"
    value: str
    line: int


@dataclass
class Block:
    type: str
    labels: tuple
    attrs: dict = field(default_factory=dict)   # nome -> tokens da expressão
    blocks: list = field(default_factory=list)
    start: int = 0
    end: int = 0


def _interpolation_end(text, j):
    depth = 1
    while j < len(text):
        c = text[j]
        if c == '"':
            j = _string_end(text, j)
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return j + 1
        j += 1
    return j


def _string_end(text, i):
    """Índice logo depois da aspa que fecha a string aberta em `i`."""
    j = i + 1
    while j < len(text):
        c = text[j]
        if c == "\\":
            j += 2
        elif c == '"':
            return j + 1
        elif c == "\n":
            return j  # string sem fechar: não engole o resto do arquivo
        elif c in "$%" and text.startswith(c + "{", j + 1):
            j += 3  # `$${` e `%%{` são o texto literal `${` e `%{`
        elif c in "$%" and text.startswith("{", j + 1):
            j = _interpolation_end(text, j + 2)
        else:
            j += 1
    return j


def tokenize(text):
    tokens, i, n, line = [], 0, len(text), 1
    while i < n:
        c = text[i]
        if c == "\n":
            line += 1
            i += 1
        elif c.isspace():
            i += 1
        elif c == "#" or text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            end = n if end < 0 else end + 2
            line += text.count("\n", i, end)
            i = end
        elif c == '"':
            end = _string_end(text, i)
            closed = end > i + 1 and text[end - 1] == '"'
            tokens.append(Token("str", text[i + 1:end - 1 if closed else end], line))
            line += text.count("\n", i, end)
            i = end
        elif text.startswith("<<", i) and (heredoc := _HEREDOC.match(text, i)):
            closing = re.compile(rf"^[ \t]*{re.escape(heredoc.group(1))}[ \t]*$", re.M)
            found = closing.search(text, heredoc.end())
            body_end = found.start() if found else n
            end = found.end() if found else n
            tokens.append(Token("str", text[heredoc.end():body_end], line))
            line += text.count("\n", i, end)
            i = end
        elif match := _IDENT.match(text, i):
            tokens.append(Token("id", match.group(), line))
            i = match.end()
        else:
            tokens.append(Token("p", c, line))
            i += 1
    return tokens


def expression(tokens, i, *, limit=None, stop_at_comma=False):
    """Tokens da expressão que começa em `i` e o índice seguinte.

    Uma expressão termina na quebra de linha fora de qualquer delimitador, na vírgula
    (dentro de um mapa) ou no `}`/`)`/`]` que fecha o contêiner dela.
    """
    limit = len(tokens) if limit is None else limit
    out, depth = [], 0
    last_line = tokens[i].line if i < limit else 0
    while i < limit:
        token = tokens[i]
        if depth == 0 and out and token.line > last_line:
            break
        if token.kind == "p":
            if token.value in "([{":
                depth += 1
            elif token.value in ")]}":
                if depth == 0:
                    break
                depth -= 1
            elif token.value == "," and depth == 0 and stop_at_comma:
                i += 1
                break
        out.append(token)
        last_line = token.line
        i += 1
    return out, i


def _body(tokens, i, top=False):
    attrs, blocks, n = {}, [], len(tokens)
    while i < n:
        token = tokens[i]
        if token.kind == "p" and token.value == "}":
            if top:
                i += 1
                continue
            return attrs, blocks, i
        if token.kind != "id":
            i += 1
            continue
        following = tokens[i + 1] if i + 1 < n else None
        if following and following.kind == "p" and following.value == "=":
            attrs[token.value], i = expression(tokens, i + 2)
            continue
        j, labels = i + 1, []
        while j < n and tokens[j].kind in ("str", "id"):
            labels.append(tokens[j].value)
            j += 1
        if j < n and tokens[j].kind == "p" and tokens[j].value == "{":
            inner_attrs, inner_blocks, close = _body(tokens, j + 1)
            end_line = tokens[close].line if close < n else token.line
            blocks.append(Block(token.value, tuple(labels), inner_attrs, inner_blocks,
                                token.line, end_line))
            i = close + 1
        else:
            i += 1
    return attrs, blocks, i


def parse(text):
    """Blocos de nível superior do arquivo (`resource`, `provider`, `locals`...)."""
    return _body(tokenize(text), 0, top=True)[1]
