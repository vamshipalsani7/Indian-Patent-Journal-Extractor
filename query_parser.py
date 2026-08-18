"""
Boolean query parser for the v6 search layer.

Grammar (precedence: NOT > AND > OR; parentheses override):
    or_expr  := and_expr (OR and_expr)*
    and_expr := not_expr (AND? not_expr)*        # adjacency = implicit AND
    not_expr := NOT not_expr | atom
    atom     := '(' or_expr ')' | '"' phrase '"' | term

AND / OR / NOT are recognised case-insensitively as operators. To search for
one of those words literally, quote it ("and"). Returns an AST of the node
classes below, or None for an empty query.
"""

import re

_LEX = re.compile(r'\s*(\(|\)|"[^"]*"|[^\s()]+)')
_OPERATORS = {"AND", "OR", "NOT"}


class Term:
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return f"Term({self.value!r})"


class Phrase:
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return f"Phrase({self.value!r})"


class And:
    def __init__(self, items):
        self.items = items

    def __repr__(self):
        return f"And({self.items!r})"


class Or:
    def __init__(self, items):
        self.items = items

    def __repr__(self):
        return f"Or({self.items!r})"


class Not:
    def __init__(self, child):
        self.child = child

    def __repr__(self):
        return f"Not({self.child!r})"


def _lex(text):
    tokens = []
    for match in _LEX.finditer(text):
        tokens.append(match.group(1))
    return tokens


class _Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def _peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _next(self):
        tok = self._peek()
        self.pos += 1
        return tok

    def _is_op(self, name):
        tok = self._peek()
        return tok is not None and tok.upper() == name and tok not in ("(", ")")

    def parse(self):
        if not self.tokens:
            return None
        node = self._parse_or()
        return node

    def _parse_or(self):
        items = [self._parse_and()]
        while self._is_op("OR"):
            self._next()
            items.append(self._parse_and())
        return items[0] if len(items) == 1 else Or(items)

    def _parse_and(self):
        items = [self._parse_not()]
        while True:
            tok = self._peek()
            if tok is None or tok == ")" or self._is_op("OR"):
                break
            if self._is_op("AND"):
                self._next()
            # else: adjacency -> implicit AND
            items.append(self._parse_not())
        return items[0] if len(items) == 1 else And(items)

    def _parse_not(self):
        if self._is_op("NOT"):
            self._next()
            return Not(self._parse_not())
        return self._parse_atom()

    def _parse_atom(self):
        tok = self._next()
        if tok == "(":
            node = self._parse_or()
            if self._peek() == ")":
                self._next()
            return node
        if tok is not None and len(tok) >= 2 and tok[0] == '"' and tok[-1] == '"':
            return Phrase(tok[1:-1])
        return Term(tok if tok is not None else "")


def parse(text):
    """Parse a query string into an AST (or None if empty)."""
    return _Parser(_lex(text or "")).parse()


def positive_terms(node):
    """Collect the positive (non-negated) Term/Phrase leaves of a query,
    used to explain why a record matched. NOT branches are excluded."""
    out = []

    def walk(n, negated):
        if n is None:
            return
        if isinstance(n, (Term, Phrase)):
            if not negated:
                out.append(n.value)
        elif isinstance(n, Not):
            walk(n.child, not negated)
        elif isinstance(n, (And, Or)):
            for item in n.items:
                walk(item, negated)

    walk(node, False)
    return out
