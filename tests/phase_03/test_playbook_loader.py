"""Phase 3: playbook format and validation (FR-PBK-001; TECHNICAL.md › Playbooks section 1; I-02, I-14)."""

from __future__ import annotations

import textwrap

import pytest

from packages.intelligence.playbooks import PlaybookError, load_all, load_playbook

VALID = """\
key: tiny_deal
version: 1
title: {en: Tiny deal, hi: छोटा सौदा}
ack_window: 5
terms:
  - key: parties
    label: {en: Parties, hi: पक्ष}
    required: true
    weight: 40
    type: party
    ask_order: 3
    parsers: []
    ambiguity: []
    pairs_with: []
    cues: {en: [], hi: []}
    model_aliases: [buyer, seller]
  - key: price
    label: {en: Price, hi: कीमत}
    required: true
    weight: 60
    type: money
    ask_order: 1
    parsers: [amounts]
    ambiguity: [approx_amount]
    pairs_with: [note]
    cues: {en: [price, rate], hi: [daam]}
    model_aliases: [unit_price]
  - key: note
    label: {en: Note, hi: टिप्पणी}
    required: false
    weight: 0
    type: text
    ask_order: 2
    parsers: []
    ambiguity: []
    pairs_with: []
    cues: {en: [note]}
    model_aliases: []
ambiguity_rules:
  - id: approx_amount
    type: AMBIGUOUS_AMOUNT
    patterns: [approx, around]
    reason: {en: "This is an approximate price.", hi: "यह अनुमानित कीमत है।"}
legal_hints: []
handshake_questions: [price, parties, note]
recap: {template_set: tiny_deal}
suggestions: {template_set: tiny_deal}
"""


def write(tmp_path, text, name="tiny_deal.yaml"):
    p = tmp_path / name
    p.write_text(textwrap.dedent(text), encoding="utf-8")
    return p


def test_valid_playbook_loads(tmp_path):
    pb = load_playbook(write(tmp_path, VALID))
    assert pb.key == "tiny_deal" and pb.version == 1
    assert [t.key for t in pb.terms] == ["parties", "price", "note"]
    assert pb.required_keys == ["parties", "price"]
    assert pb.term("price").weight == 60
    assert pb.term("price").cues["en"] == ["price", "rate"]
    assert pb.term("price").model_aliases == ["unit_price"]
    assert pb.ack_window == 5


def test_alias_lookup_maps_model_keys_to_playbook_keys(tmp_path):
    pb = load_playbook(write(tmp_path, VALID))
    assert pb.key_for_alias("unit_price") == "price"
    assert pb.key_for_alias("buyer") == "parties"
    assert pb.key_for_alias("price") == "price"
    assert pb.key_for_alias("unknown") is None


def test_new_playbook_in_folder_appears_without_code_change(tmp_path):
    write(tmp_path, VALID)
    write(tmp_path, VALID.replace("key: tiny_deal", "key: other_deal"), name="other_deal.yaml")
    assert set(load_all(tmp_path)) == {"tiny_deal", "other_deal"}


def _broken(old: str, new: str) -> str:
    assert old in VALID
    return VALID.replace(old, new, 1)


@pytest.mark.parametrize(
    "old,new,line_hint",
    [
        ("weight: 60", "weight: 50", None),  # weights no longer sum to 100
        ("type: money", "type: banana", "type: banana"),
        ("parsers: [amounts]", "parsers: [no_such_parser]", "no_such_parser"),
        ("ambiguity: [approx_amount]", "ambiguity: [missing_rule]", "missing_rule"),
        ("pairs_with: [note]", "pairs_with: [ghost]", "ghost"),
        ("handshake_questions: [price, parties, note]", "handshake_questions: [price, parties]", None),
        ("handshake_questions: [price, parties, note]", "handshake_questions: [price, parties, note, ghost]", None),
        ("required: false\n    weight: 0", "required: false\n    weight: 5", None),
        ("title: {en: Tiny deal, hi: छोटा सौदा}", "title: {en: Tiny deal}", None),
        ("  - key: note", "  - key: price", None),  # duplicate term key
    ],
)
def test_invalid_playbooks_refused(tmp_path, old, new, line_hint):
    path = write(tmp_path, _broken(old, new))
    with pytest.raises(PlaybookError) as err:
        load_playbook(path)
    assert err.value.line is not None and err.value.line >= 1
    if line_hint:
        lines = path.read_text(encoding="utf-8").splitlines()
        assert line_hint in lines[err.value.line - 1], "the error names the offending line"


def test_yaml_syntax_error_reports_line(tmp_path):
    path = write(tmp_path, VALID + "terms: [unclosed\n")
    with pytest.raises(PlaybookError) as err:
        load_playbook(path)
    assert err.value.line is not None


def test_ack_window_defaults_to_five(tmp_path):
    pb = load_playbook(write(tmp_path, VALID.replace("ack_window: 5\n", "")))
    assert pb.ack_window == 5


@pytest.mark.parametrize(
    "old,new,line_hint",
    [
        ("version: 1", "version: 1\nsurprise: 1", "surprise"),  # unknown top-level field
        ("model_aliases: [unit_price]", "model_aliases: [buyer]", "buyer"),  # alias already used by another term
        ("legal_hints: []", "legal_hints:\n  - id: h1\n    when: {term_missing: ghost}\n    text: {en: Ask., hi: पूछें।}", "ghost"),
        ("parsers: [amounts]", "parsers: amounts", "amounts"),  # must be a list
        ("ask_order: 1", "ask_order: first", "first"),
        ("cues: {en: [price, rate], hi: [daam]}", "cues: {hi: [daam]}", None),
    ],
)
def test_more_invalid_playbooks_refused(tmp_path, old, new, line_hint):
    path = write(tmp_path, _broken(old, new))
    with pytest.raises(PlaybookError) as err:
        load_playbook(path)
    assert err.value.line is not None and err.value.line >= 1
    if line_hint:
        assert line_hint in path.read_text(encoding="utf-8").splitlines()[err.value.line - 1]


def test_duplicate_yaml_key_names_its_line(tmp_path):
    path = write(tmp_path, VALID + "version: 2\n")
    with pytest.raises(PlaybookError) as err:
        load_playbook(path)
    assert "version" in path.read_text(encoding="utf-8").splitlines()[err.value.line - 1]


def test_empty_file_refused(tmp_path):
    with pytest.raises(PlaybookError):
        load_playbook(write(tmp_path, ""))


def test_error_message_carries_the_line(tmp_path):
    with pytest.raises(PlaybookError) as err:
        load_playbook(write(tmp_path, _broken("type: money", "type: banana")))
    assert f"line {err.value.line}" in str(err.value) and "banana" in err.value.message


def test_unknown_playbook_key_is_a_key_error(tmp_path):
    write(tmp_path, VALID)
    with pytest.raises(KeyError, match="no_such_deal"):
        load_all(tmp_path)["no_such_deal"]


def test_two_files_with_the_same_key_refused(tmp_path):
    write(tmp_path, VALID)
    write(tmp_path, VALID, name="copy.yaml")
    with pytest.raises(PlaybookError):
        load_all(tmp_path)


def test_legal_hint_conditions_are_loaded(tmp_path):
    text = VALID.replace(
        "legal_hints: []",
        "legal_hints:\n  - id: h1\n    when: {keywords: [flat], term_missing: note}\n    text: {en: Ask., hi: पूछें।}\n  - id: h2\n    text: {en: Always., hi: हमेशा।}",
    )
    pb = load_playbook(write(tmp_path, text))
    assert (pb.legal_hints[0].keywords, pb.legal_hints[0].term_missing) == (["flat"], "note")
    assert (pb.legal_hints[1].keywords, pb.legal_hints[1].term_missing) == ([], None)
    assert pb.rule("approx_amount").type == "AMBIGUOUS_AMOUNT" and pb.rule("nope") is None
    with pytest.raises(KeyError):
        pb.term("nope")


def test_playbook_contains_no_code(tmp_path):
    with pytest.raises(PlaybookError):
        load_playbook(write(tmp_path, VALID + "python: !!python/object/apply:os.system ['echo hi']\n"))
