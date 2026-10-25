"""Phase 4: every rankable gap has templates in every tone and language (no TemplateMissing at run time)."""

from __future__ import annotations

import itertools

import pytest

from packages.contracts import Tone
from packages.intelligence.suggest import build_suggestion, load_templates


@pytest.mark.parametrize("lang", ["en", "hi"])
@pytest.mark.parametrize("pb_name", ["supply_playbook", "freelance_playbook"])
def test_single_and_paired_targets_render(request, pb_name, lang):
    pb = request.getfixturevalue(pb_name)
    load_templates(pb.key, lang)  # must exist
    required = pb.required_keys
    combos = [[k] for k in required]
    combos += [[a, b] for a, b in itertools.permutations(required, 2) if b in pb.term(a).pairs_with]
    for targets in combos:
        for tone in Tone:
            s = build_suggestion(targets, tone, {}, pb, lang)
            assert s.text.strip(), (targets, tone, lang)
            assert "{" not in s.text and "}" not in s.text


@pytest.mark.parametrize("lang", ["en", "hi"])
def test_flag_reason_templates_exist(lang, playbooks_dir):
    assert (playbooks_dir / "templates" / lang / "flags.yaml").is_file()
