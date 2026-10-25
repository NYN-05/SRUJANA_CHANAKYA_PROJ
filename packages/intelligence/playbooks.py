"""Playbooks as validated data (ADR-016, FR-PBK-001; TECHNICAL.md › Playbooks section 1; I-02, I-14).

A playbook is a YAML file with no code. Every error names the line it came from. Parser names refer to
code registered in ``packages.intelligence.rules``; a new playbook needs no engine change.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .rules import PARSERS

TERM_TYPES = frozenset({"party", "text", "quantity", "money", "date", "percent", "duration", "enum"})
RULE_TYPES = frozenset({"AMBIGUOUS_DATE", "AMBIGUOUS_AMOUNT", "VAGUE_QUANTITY", "VAGUE_PAYMENT"})
_TAGS = {f"tag:yaml.org,2002:{t}" for t in ("str", "int", "float", "bool", "null", "map", "seq")}
_SNAKE = re.compile(r"[a-z][a-z0-9_]*")


class PlaybookError(Exception):
    """An invalid playbook. ``line`` is the 1-based line in the file."""

    def __init__(self, message: str, line: int | None = None) -> None:
        super().__init__(f"line {line}: {message}" if line else message)
        self.message = message
        self.line = line


@dataclass(frozen=True)
class Term:
    key: str
    label: dict[str, str]
    required: bool
    weight: int
    type: str
    ask_order: int
    parsers: list[str]
    ambiguity: list[str]
    pairs_with: list[str]
    cues: dict[str, list[str]]
    model_aliases: list[str]


@dataclass(frozen=True)
class AmbiguityRule:
    id: str
    type: str
    patterns: list[str]
    reason: dict[str, str]


@dataclass(frozen=True)
class LegalHint:
    id: str
    keywords: list[str]  # shown when any appears in the confirmed terms or messages
    term_missing: str | None  # shown when this term has no accepted value
    text: dict[str, str]


@dataclass(frozen=True)
class Playbook:
    key: str
    version: int
    title: dict[str, str]
    ack_window: int
    terms: list[Term]
    ambiguity_rules: list[AmbiguityRule]
    legal_hints: list[LegalHint]
    handshake_questions: list[str]
    recap_template_set: str
    suggestions_template_set: str
    _by_key: dict[str, Term] = field(default_factory=dict, repr=False, compare=False)

    def term(self, key: str) -> Term:
        return self._by_key[key]

    @property
    def required_keys(self) -> list[str]:
        return [t.key for t in self.terms if t.required]

    def rule(self, rule_id: str) -> AmbiguityRule | None:
        return next((r for r in self.ambiguity_rules if r.id == rule_id), None)

    def key_for_alias(self, alias: str) -> str | None:
        """Map a model's key (I-02) onto the playbook key; a playbook key maps to itself."""
        if alias in self._by_key:
            return alias
        return next((t.key for t in self.terms if alias in t.model_aliases), None)


class _Reader:
    """Plain data from the YAML node tree, remembering the line of every value."""

    def __init__(self, text: str) -> None:
        self.lines: dict[tuple[Any, ...], int] = {}
        self._loader = yaml.SafeLoader("")
        try:
            root = yaml.compose(text, Loader=yaml.SafeLoader)
        except yaml.YAMLError as exc:
            mark = getattr(exc, "problem_mark", None)
            raise PlaybookError(f"invalid YAML: {getattr(exc, 'problem', exc)}", mark.line + 1 if mark else 1) from exc
        if root is None:
            raise PlaybookError("the playbook is empty", 1)
        self.data = self._convert(root, ())

    def _convert(self, node: yaml.Node, path: tuple[Any, ...]) -> Any:
        line = node.start_mark.line + 1
        self.lines[path] = line
        if node.tag not in _TAGS:
            raise PlaybookError(f"tag {node.tag!r} is not allowed; a playbook contains no code", line)
        if isinstance(node, yaml.MappingNode):
            out: dict[str, Any] = {}
            for knode, vnode in node.value:
                key = self._convert(knode, path + ("<key>",))
                if not isinstance(key, str):
                    raise PlaybookError("keys must be text", knode.start_mark.line + 1)
                if key in out:
                    raise PlaybookError(f"duplicate key {key!r}", knode.start_mark.line + 1)
                out[key] = self._convert(vnode, path + (key,))
            return out
        if isinstance(node, yaml.SequenceNode):
            return [self._convert(v, path + (i,)) for i, v in enumerate(node.value)]
        return self._loader.construct_object(node, deep=True)

    def fail(self, path: tuple[Any, ...], message: str) -> PlaybookError:
        while path and path not in self.lines:
            path = path[:-1]
        return PlaybookError(message, self.lines.get(path, 1))


def _get(r: _Reader, obj: dict[str, Any], path: tuple[Any, ...], key: str, kind: type | tuple[type, ...], *, default: Any = ...) -> Any:
    if key not in obj:
        if default is ...:
            raise r.fail(path, f"missing {key!r}")
        return default
    value = obj[key]
    if isinstance(value, bool) and kind is not bool:
        raise r.fail(path + (key,), f"{key!r} must not be a yes/no value")
    if not isinstance(value, kind):
        names = kind.__name__ if isinstance(kind, type) else " or ".join(k.__name__ for k in kind)
        raise r.fail(path + (key,), f"{key!r} must be {names}")
    return value


def _only(r: _Reader, obj: dict[str, Any], path: tuple[Any, ...], allowed: set[str]) -> None:
    for key in obj:
        if key not in allowed:
            raise r.fail(path + (key,), f"unknown field {key!r}")


def _texts(r: _Reader, obj: dict[str, Any], path: tuple[Any, ...], key: str, *, hi_required: bool = True) -> dict[str, str]:
    """A ``{en, hi}`` map of non-empty strings (rule 3: every user-facing string has English and Hindi)."""
    value = _get(r, obj, path, key, dict)
    out: dict[str, str] = {}
    for lang in ("en", "hi") if hi_required else ("en",):
        item = value.get(lang)
        if not isinstance(item, str) or not item.strip():
            raise r.fail(path + (key,), f"{key!r} needs a non-empty {lang!r} text")
        out[lang] = item
    return out


def _strings(r: _Reader, obj: dict[str, Any], path: tuple[Any, ...], key: str, *, default: Any = ...) -> list[str]:
    value = _get(r, obj, path, key, list, default=default)
    for i, item in enumerate(value):
        if not isinstance(item, str):
            raise r.fail(path + (key, i), f"{key!r} entries must be text")
    return list(value)


def _key(r: _Reader, obj: dict[str, Any], path: tuple[Any, ...], name: str = "key") -> str:
    value = _get(r, obj, path, name, str)
    if not _SNAKE.fullmatch(value):
        raise r.fail(path + (name,), f"{name!r} must be snake_case")
    return value


def _term(r: _Reader, obj: Any, path: tuple[Any, ...]) -> Term:
    if not isinstance(obj, dict):
        raise r.fail(path, "a term must be a mapping")
    _only(r, obj, path, {"key", "label", "required", "weight", "type", "ask_order", "parsers", "ambiguity", "pairs_with", "cues", "model_aliases"})
    required = _get(r, obj, path, "required", bool)
    weight = _get(r, obj, path, "weight", int)
    if weight < 0:
        raise r.fail(path + ("weight",), "weight must not be negative")
    if not required and weight != 0:
        raise r.fail(path + ("weight",), "a term that is not required has weight 0")
    typ = _get(r, obj, path, "type", str)
    if typ not in TERM_TYPES:
        raise r.fail(path + ("type",), f"type {typ!r} is not one of {sorted(TERM_TYPES)}")
    parsers = _strings(r, obj, path, "parsers", default=[])
    for i, name in enumerate(parsers):
        if name not in PARSERS:
            raise r.fail(path + ("parsers", i), f"parser {name!r} is not registered")
    cues = _get(r, obj, path, "cues", dict)
    if not set(cues) <= {"en", "hi"} or not isinstance(cues.get("en"), list):
        raise r.fail(path + ("cues",), "cues needs an 'en' list and may have a 'hi' list")
    for lang, words in cues.items():
        if not isinstance(words, list) or not all(isinstance(w, str) and w.strip() for w in words):
            raise r.fail(path + ("cues", lang), "cue words must be non-empty text")
    return Term(
        key=_key(r, obj, path),
        label=_texts(r, obj, path, "label"),
        required=required,
        weight=weight,
        type=typ,
        ask_order=_get(r, obj, path, "ask_order", int),
        parsers=parsers,
        ambiguity=_strings(r, obj, path, "ambiguity", default=[]),
        pairs_with=_strings(r, obj, path, "pairs_with", default=[]),
        cues={"en": list(cues["en"]), "hi": list(cues.get("hi") or [])},
        model_aliases=_strings(r, obj, path, "model_aliases", default=[]),
    )


def _rule(r: _Reader, obj: Any, path: tuple[Any, ...]) -> AmbiguityRule:
    if not isinstance(obj, dict):
        raise r.fail(path, "an ambiguity rule must be a mapping")
    _only(r, obj, path, {"id", "type", "patterns", "reason"})
    typ = _get(r, obj, path, "type", str)
    if typ not in RULE_TYPES:
        raise r.fail(path + ("type",), f"type {typ!r} is not one of {sorted(RULE_TYPES)}")
    return AmbiguityRule(_key(r, obj, path, "id"), typ, _strings(r, obj, path, "patterns", default=[]), _texts(r, obj, path, "reason"))


def _hint(r: _Reader, obj: Any, path: tuple[Any, ...]) -> LegalHint:
    if not isinstance(obj, dict):
        raise r.fail(path, "a legal hint must be a mapping")
    _only(r, obj, path, {"id", "when", "text"})
    when = _get(r, obj, path, "when", dict, default={})
    _only(r, when, path + ("when",), {"keywords", "term_missing"})
    missing = when.get("term_missing")
    if missing is not None and not isinstance(missing, str):
        raise r.fail(path + ("when", "term_missing"), "term_missing must be a term key")
    return LegalHint(_key(r, obj, path, "id"), _strings(r, when, path + ("when",), "keywords", default=[]), missing, _texts(r, obj, path, "text"))


def _template_set(r: _Reader, data: dict[str, Any], key: str) -> str:
    block = _get(r, data, (), key, dict)
    _only(r, block, (key,), {"template_set"})
    return _key(r, block, (key,), "template_set")


def _unique(r: _Reader, seen: dict[str, int], value: str, path: tuple[Any, ...], what: str) -> None:
    if value in seen:
        raise r.fail(path, f"duplicate {what} {value!r}")
    seen[value] = 1


def _build(r: _Reader) -> Playbook:
    data = r.data
    if not isinstance(data, dict):
        raise r.fail((), "a playbook is a mapping")
    _only(r, data, (), {"key", "version", "title", "ack_window", "terms", "ambiguity_rules", "legal_hints", "handshake_questions", "recap", "suggestions"})
    version = _get(r, data, (), "version", int)
    ack_window = _get(r, data, (), "ack_window", int, default=5)
    if version < 1 or ack_window < 1:
        raise r.fail(("version" if version < 1 else "ack_window",), "must be 1 or more")
    raw_terms = _get(r, data, (), "terms", list)
    if not raw_terms:
        raise r.fail(("terms",), "a playbook needs at least one term")
    terms, seen = [], {}
    for i, raw in enumerate(raw_terms):
        term = _term(r, raw, ("terms", i))
        _unique(r, seen, term.key, ("terms", i, "key"), "term key")
        terms.append(term)
    total = sum(t.weight for t in terms if t.required)
    if total != 100:
        raise r.fail(("terms",), f"weights of required terms must sum to 100 (they sum to {total})")

    rules, rule_ids = [], {}
    for i, raw in enumerate(_get(r, data, (), "ambiguity_rules", list, default=[])):
        rule = _rule(r, raw, ("ambiguity_rules", i))
        _unique(r, rule_ids, rule.id, ("ambiguity_rules", i, "id"), "rule id")
        rules.append(rule)
    hints, hint_ids = [], {}
    for i, raw in enumerate(_get(r, data, (), "legal_hints", list, default=[])):
        hint = _hint(r, raw, ("legal_hints", i))
        _unique(r, hint_ids, hint.id, ("legal_hints", i, "id"), "hint id")
        if hint.term_missing is not None and hint.term_missing not in seen:
            raise r.fail(("legal_hints", i, "when", "term_missing"), f"unknown term {hint.term_missing!r}")
        hints.append(hint)

    aliases: dict[str, str] = {}
    for i, term in enumerate(terms):
        for j, name in enumerate(term.ambiguity):
            if name not in rule_ids:
                raise r.fail(("terms", i, "ambiguity", j), f"ambiguity rule {name!r} is not defined")
        for j, name in enumerate(term.pairs_with):
            if name not in seen:
                raise r.fail(("terms", i, "pairs_with", j), f"unknown term {name!r}")
        for j, name in enumerate(term.model_aliases):
            if name in aliases or (name in seen and name != term.key):
                raise r.fail(("terms", i, "model_aliases", j), f"alias {name!r} is already used")
            aliases[name] = term.key
    questions = _strings(r, data, (), "handshake_questions")
    if not 3 <= len(questions) <= 4:
        raise r.fail(("handshake_questions",), "handshake_questions needs 3 or 4 term keys")
    for j, name in enumerate(questions):
        if name not in seen:
            raise r.fail(("handshake_questions", j), f"unknown term {name!r}")
    return Playbook(
        key=_key(r, data, ()),
        version=version,
        title=_texts(r, data, (), "title"),
        ack_window=ack_window,
        terms=terms,
        ambiguity_rules=rules,
        legal_hints=hints,
        handshake_questions=questions,
        recap_template_set=_template_set(r, data, "recap"),
        suggestions_template_set=_template_set(r, data, "suggestions"),
        _by_key={t.key: t for t in terms},
    )


def load_playbook(path: str | Path) -> Playbook:
    """Load and validate one playbook file; raises PlaybookError naming the line."""
    return _build(_Reader(Path(path).read_text(encoding="utf-8")))


def load_all(directory: str | Path) -> dict[str, Playbook]:
    """Every ``*.yaml`` playbook in a folder, by key. An unknown key raises KeyError with the key."""
    books: dict[str, Playbook] = {}
    for path in sorted(Path(directory).glob("*.yaml")):
        book = load_playbook(path)
        if book.key in books:
            raise PlaybookError(f"{path.name}: playbook key {book.key!r} is already defined", 1)
        books[book.key] = book
    return books
