# Changes

Newest entries at the bottom. Each entry records the date and time, the phase, the files touched and what changed. Nothing here claims that a test passed; tests are run and verified separately.

---

## 2026-10-25 17:10 +05:30 — Phase 1: Contracts and integrity core

Implemented PHASES.md Phase 1 (tasks 1 to 9). Not executed or verified. Phase 0 (`pyproject.toml` with `pydantic` and `rfc8785`, settings, the API skeleton) has not been built yet, and the Phase 1 gate runs Phase 0 too.

### Added
- `packages/__init__.py`: makes `packages` an importable package (the layout Phase 0 also requires).
- `packages/contracts/__init__.py`: every Appendix A.1 contract. Enums: `TermState` and `TERM_STATE_LABELS`, `Origin`, `MessageOrigin`, `FlagType` (PRD 8.4), `Tone`, `ConfirmationState`. Models: `Message`, `ImportRecord`; the term values `MoneyValue`, `DateValue`, `PartialDateValue`, `QuantityValue`, `PercentValue`, `TextValue`, `EventValue`, `PartyValue`, `PaymentValue`, joined in a `kind`-discriminated `TermValue`; `SourceRef`, `Candidate`, `ProposedTerm`, `AgreedTerm`, `Flag`, `ScoreRow`, `ScoreResult`, `Suggestion`, `RecapLine`, `RecapDraft`, `Recap`, `FirstDifference` (including kind `root`, I-21), `VerifyCheck`, `VerifyResult`. Also `CONTRACT_VERSION = "1.0"` and `parse_timestamp`.
  - Validation: timestamps must be `YYYY-MM-DDTHH:MM:SS±HH:MM` with ASCII digits only; `Z`, a missing offset, fractional seconds, `-00:00` and impossible dates or offsets are rejected. Paise is a canonical digit string. Hashes are 64 lowercase hex. `seq >= 1`. A source span has `end >= start`. An echo code uses Crockford base32 only. Unknown fields are rejected (`extra="forbid"`).
  - `contracts/formatting.py` is not added; it is Phase 4.
- `packages/integrity/__init__.py`.
- `packages/integrity/hashing.py`: `TypeByte` (INTEGRITY_SPEC 3), `SALTED_TYPES`, `PLAIN_TYPES`, `sha256`, `normalize_text` (NFC plus line endings; nothing trimmed), `normalize_record` (values only, keys untouched, input not mutated), `canonicalize` (RFC 8785 via `rfc8785`), `record_bytes`, `payload_digest_json`, `payload_digest_bytes`, `leaf_hash`, `plain_hash`, `require_bytes`, `CanonicalizationError` (a `ValueError`).
  - `canonicalize` rejects integers outside ±(2^53−1), NaN and infinities, non-string keys and non-JSON types.
  - `leaf_hash` and `plain_hash` reject a wrong salt or digest size, the reserved byte `0x00`, unknown bytes, and a salted type used in plain form or the reverse.
- `packages/integrity/merkle.py`: `merkle_root`, `inclusion_proof` and `verify_inclusion`, plus `EmptyTreeError`. An odd last node is carried up and never duplicated. A carried level adds no proof entry. A one-leaf root is the leaf itself. Leaves must be 32 raw bytes. An unknown proof side fails verification.
- `packages/integrity/chain.py`: `terms_digest` (`0x20`) and `chain_link` (`0x30`). `link_0` uses 32 zero bytes, and every operand must be 32 raw bytes.
- `packages/integrity/echo.py`: `ALPHABET`, `recap_hash` (`0x21`), `echo_code` (first 20 bits of `H(0x50 ‖ recap_hash)`), `extract_code` and `codes_match`. Per I-08, the reply is normalised (NFC, upper case, spaces collapsed), `CONFIRM` is found first, and `O→0` and `I/L→1` are mapped on the code token only. A token with a character outside the alphabet, such as `U`, gives no code.
- `packages/integrity/timestamp.py`: `format_timestamp` (rejects naive datetimes, fractional seconds and offsets with a seconds part; UTC is written `+00:00`) and `parse_timestamp`, re-exported from the contracts so there is a single parser.
- `packages/integrity/receipt.py`: `receipt_hash(body)` (`0x40`, body only) and `SPEC_VERSION = "1.1"`. Version 1.1 records the I-09 change, which adds `import_record_hash` to the receipt body; byte values are unchanged.
- `apps/verify/integrity.mjs`: the same primitives in vanilla JavaScript with WebCrypto, an inline RFC 8785 canonicaliser, no dependencies and no network.
  - Exports: `sha256`, `canonicalize`, `normalizeText`, `normalizeRecord`, `payloadDigestJson`, `leafHash`, `plainHash`, `merkleRoot`, `inclusionProof`, `verifyInclusion`, `termsDigest`, `chainLink`, `recapHash`, `echoCode`, `extractCode`, `codesMatch`, `parseTimestamp` (returns `{date, offsetMinutes}`; throws) and `formatTimestamp(date, offsetMinutes)`, plus `TYPE_BYTE`, `SALTED_TYPES`, `PLAIN_TYPES` and `ALPHABET`.
- `scripts/make_test_vectors.py`: builds `test-vectors/integrity/{sha256,jcs,normalize,leaves,plain,merkle,chain,echo,timestamp,worked_example}.json` from the Python code in the Appendix B format, with `only: "python"` on number cases JavaScript cannot represent.
  - It also rewrites the worked-example table in `DOCS/TECHNICAL.md` between the `worked-example` markers.
  - `--check` regenerates everything in memory and exits 1 if any file or the table differs.
  - The vector files are **not committed yet**. Run `uv run python scripts/make_test_vectors.py` once to write them.

### Modified
- `DOCS/TECHNICAL.md` (Integrity Specification), following the change rule in section 15:
  - Sections 4.2 and 9 add the `import_record_hash` receipt-body field (I-09) and note `spec_version` 1.1.
  - The worked example now gives the message ids and times (10:02, 10:04, 10:05 `+05:30`). These reproduce the published leaf 3, and the generator needs them to recompute leaf 3.
- `tests/phase_01/test_contracts.py`: added tests for:
  - unknown-field rejection;
  - partial dates (leap day, impossible days);
  - canonical ASCII paise;
  - source-span order and `seq`;
  - the `kind` discriminator and `PaymentValue.when`;
  - the echo-code alphabet on `Recap`;
  - the `VerifyResult` and `FirstDifference` shapes;
  - a single timestamp parser.
- `tests/phase_01/test_merkle.py`: an unknown proof side fails; `EmptyTreeError` is a `ValueError`; a proof on an empty tree and a negative index are rejected.
- `tests/phase_01/test_timestamp.py`: offsets with seconds are rejected, as are non-ASCII digits and a trailing newline; added a round trip across offsets.
- `tests/phase_01/test_jcs.py`: nested invalid values, tuples and sets are rejected; `CanonicalizationError` is a `ValueError`; booleans are not integers.
- `tests/phase_01/test_vectors.py`:
  - generator `--check` detects a changed vector file and a stale spec table (run in a temp directory);
  - the spec table matches `worked_example.json`;
  - every vector file carries the current `SPEC_VERSION`.
- `tests/phase_01/js/integrity.test.mjs`:
  - added tests for the timestamp round trip, non-JSON rejection and UTF-16 key order in `canonicalize`, normalisation, inclusion-proof verification and tampering, code-token mapping, and 32-byte operand checks;
  - the run comment now uses the quoted glob.
- `changes.md` renamed to `CHANGES.md`; it was empty.

---

## 2026-10-25 17:22 +05:30 — Phase 2: WhatsApp chat ingest

Implemented PHASES.md Phase 2 (tasks 1 to 10). Not executed or verified. Nothing in this phase writes to disk or a database; the vault write is Phase 5.

### Added
- `packages/ingest/__init__.py`.
- `packages/ingest/errors.py`: `ImportRefused(code)` with the codes `empty`, `binary`, `too_large`, `not_whatsapp`, `bad_zip`, `no_chat_file` and `zip_limits`. An unknown code is a `ValueError`.
- `packages/ingest/whatsapp.py`: `parse_export(data, *, date_order=None, utc_offset="+05:30") -> ParseResult`, plus the `ParsedEntry` and `ParseResult` shapes from Appendix E. `bytes` input is a file and `str` input is pasted text, through the same parser.
  - **Headers:** anchored, linear-time headers for Android (`D/M/YY, H:MM - `, 12- and 24-hour, `am/pm`, U+202F or NBSP before the marker, 4-digit years accepted) and iPhone (`[D/M/YYYY, H:MM:SS] `, 12-hour, with a leading U+200E).
  - **Text cleanup:** BOM, CRLF and CR are normalised.
  - **Kinds:** `text`, `media` (`<Media omitted>`, `<attached: NAME>`, `NAME (file attached)`, `image/audio/video/document/sticker/GIF omitted`, with the attachment name captured), `deleted`, and `system`.
  - **System notices:** known notices are checked before splitting on the first `": "`. A notice with a subject only counts when the subject has no `": "`, so "Ravi: left" stays a message. On iPhone, a body that starts with U+200E and matches a notice is a notice with the chat name as its sender. A header with no `Sender:` part is treated as a system notice.
  - **Continuation lines** join the previous message, and trailing blank lines are dropped.
  - **Header-shaped lines** whose date or time cannot exist, or whose date is impossible under an explicit date order, are listed as unparsed and not joined to the previous message.
  - **Date order:** inferred as `DMY` if any first field is above 12 and `MDY` if any second field is above 12. Both gives warning `mixed_date_order` and order `None`. With no order, timestamps are `None` and `needs_date_order_choice=True`. An explicit `date_order` always wins.
  - **Participants** are listed in order of first appearance; system lines add none.
  - **Numbering:** `seq` is 1-based over every entry, system lines included (I-10).
  - **Refusals:** NUL bytes give `binary`. Invalid UTF-8 above 1% of the bytes gives `binary`, but a single invalid sequence is always tolerated with warning `invalid_utf8`. This keeps the existing test, which has 1 bad byte in 65 bytes, within "rare". Empty or whitespace-only input gives `empty`, and input with no header line gives `not_whatsapp`. Other errors raise nothing except `ImportRefused`, apart from `ValueError` for a bad `date_order` or `utc_offset` argument.
- `packages/ingest/preview.py`: `build_preview(data, file_name, *, max_bytes, date_order=None) -> ImportPreview`.
  - Input over `max_bytes` gives `too_large`, checked on the raw bytes first.
  - `message_count` counts text entries only; `media_count` is shown separately.
  - `date_range` is `(None, None)` while the date order is unknown.
  - `format_problem` is set below 80% parsed lines, with at most 5 unparsed lines and their line numbers.
  - `export_digest` is the SHA-256 hex of the raw bytes, with no normalisation.
  - The preview is a frozen, comparable dataclass and creates nothing.
- `packages/ingest/commit.py`: `prepare_commit(parse_result, *, me, counterparty, playbook_key, origin, deal_id=None) -> DealDraft`, plus `Participant`, `DealDraft` and `SelectionError`.
  - **Refused with `SelectionError`:** a missing, unknown or identical party choice, or a date order that is still unknown.
  - **Messages:** contract `Message` objects with a UUID each. Timestamps are written `YYYY-MM-DDTHH:MM:SS+HH:MM` and never `Z`. System entries get `sender_id=None`, and `attachment_hash` stays `None` until Phase 5 stores the media.
  - **Participant ids** are the exported display names, as the Phase 3 test `parties.value.names == [d.me_id, d.counterparty_id]` expects. The two chosen parties have role `party`; everyone else is `context`.
  - **Term sources:** `eligible_message_ids` holds only `text` entries from the two parties.
- `packages/ingest/archive.py`: `read_export_zip(data, *, max_total_bytes, max_ratio=100, max_entries=2000) -> ZipExport`.
  - **Reading:** entries are streamed in 64 KiB chunks, and the actual decompressed bytes count against the total cap. The ratio cap applies to entries above 1 MiB, so a short, highly compressible chat text is not mistaken for a bomb. Too many entries, too many bytes or too high a ratio gives `zip_limits`.
  - **Unsafe entries:** names with `..`, absolute paths, drive letters or backslashes are rejected and listed as `(name, "unsafe_path")`, and the import continues without them.
  - **Chat discovery:** exactly one `_chat.txt` or `WhatsApp Chat*.txt` is the chat; otherwise, the only `.txt` file. Anything else gives `no_chat_file`.
  - **Media:** keyed by base name. The first of two duplicates is kept with warning `duplicate_entry:<name>`. `unmatched_media` and `missing_media` come from the attachment names the parser finds in the chat text.
  - **Errors:** a corrupt, encrypted or unsupported archive or entry gives `bad_zip`. Nothing is extracted to disk.
- `packages/ingest/samples.py`: `list_samples()` and `load_sample(name)`. Only listed names are accepted (`KeyError` otherwise), so no path is ever built from input.
- `packages/ingest/samples/{clean,ambiguous,contradictory}.txt`: the three synthetic samples, byte-identical to `tests/fixtures/chats/`.
- `eval/chats/sample_{clean,ambiguous,contradictory}.txt` and `eval/labels/sample_{clean,ambiguous,contradictory}.json`: the gold labels for the samples (FR-IMP-007), in the Phase 10 label format. Values are contract value objects and sources are message `seq` numbers. The flags are the expected AMBIGUOUS_DATE, MISSING_TERM and CONTRADICTION.

### Modified
- `packages/contracts/__init__.py`: `Message.sender_id` is now `str | None`. System notices have no sender, which the Phase 2 test `system[0].sender_id is None` requires; the field is still hashed per INTEGRITY_SPEC 4.2.
- `tests/phase_02/test_archive.py`:
  - The unsafe-path test now accepts the `/` spelling of a backslash name, because `zipfile` rewrites `\` to `/` in entry names on Windows.
  - Added tests: a single non-standard `.txt` file is the chat; two unnamed `.txt` files are ambiguous; a named chat wins over other `.txt` files; media in a subfolder is matched by name; a corrupt entry is refused; a small, highly compressible chat is not a bomb; nothing is extracted to disk.
- `tests/phase_02/test_android_format.py`: added tests for:
  - "left" and "added" inside messages (not notices);
  - impossible headers are unparsed, not joined;
  - invalid times are not headers;
  - a sender without a trailing space gives empty text;
  - media with a caption;
  - an invalid `utc_offset`;
  - 4-digit Android years.
- `tests/phase_02/test_iphone_format.py`: an iPhone notice with the chat name as sender; an iPhone deleted message.
- `tests/phase_02/test_malformed.py`: frequent invalid UTF-8 gives `binary`; pasted text with NUL gives `binary`; the size cap is checked before parsing; unknown refusal codes are rejected; `parse_ratio` is reported.
- `tests/phase_02/test_preview_and_commit.py`: no date range while the order is unknown; a UUID deal id by default; committed timestamps for 12-hour clocks; `prepare_commit` writes nothing.
- `tests/phase_02/test_samples.py`: sample names cannot escape the folder; the three copies of each sample are identical; each gold label is consistent with its chat.

---

## 2026-10-25 17:52 +05:30 — Phase 3: Playbooks and the deterministic rules engine

Implemented PHASES.md Phase 3 (tasks 1 to 10). Not executed or verified. One YAML syntax check of the two playbook files was run while writing them; nothing else was run, and no test has been executed. Phase 0 (`pyproject.toml` with `pyyaml`) is still not built, and the Phase 3 gate runs Phases 0 to 2 as well.

### Added
- `packages/intelligence/__init__.py`.
- `packages/intelligence/normalize.py`: `normalize_for_rules(text)` (NFC, Devanagari, Kannada and full-width digits to ASCII, whitespace collapsed and trimmed) and `normalize(text) -> Normalized`. `Normalized` keeps the original span of every normalised character, so every parser reports spans in the original text.
- `packages/intelligence/injection.py`: `INJECTION_PATTERNS` and `is_injection(text)` (I-23). The Phase 8 grounding step will reuse and extend this list.
- `packages/intelligence/rules/` (one module per parser, all deterministic and never raising):
  - `base.py`: the `Match` base (span in the original text) and shared boundary patterns.
  - `amounts.py`: `parse_amounts(text, *, units=())`.
    - Forms: `50k`, `1.5 lakh`, `2 crore`, `₹`/`Rs.`/`INR` prefixes and suffixes, `/-`, Indian grouping, decimals, Hindi number words with a magnitude (`pachaas hazaar`, `dedh lakh`, `dhai lakh`, Devanagari forms), ranges (`40 to 50k`, `40-50k`), approximate markers (`approx`, `around`, `about`, `lagbhag`, `~`), and foreign currencies marked `currency != "INR"`.
    - Cues: a bare number is money only with a currency marker, a magnitude word or a cue word next to it. `units` adds unit words so "2 revisions" is not money. An approximate marker alone counts as a cue only for amounts of ₹1,000 or more.
    - Never money: a number followed by a unit, a month name or a duration word (so "advance 20 Oct" and "30 din baad" are not money); numbers of 10 or more digits without a currency marker; times, dates, `#ids` and percentages.
    - Fields: `paise`, `currency`, `per` (`item`/`total`), `approximate`, `is_range`, `low_paise`, `high_paise`, `cue`, `period` (for "500 per day").
  - `quantities.py`: `parse_quantities(text, *, units=())` with a built-in unit list that playbook unit words extend, `dozen` (x12), vague forms (`some`/`a few`/`several` with a unit, `as needed`, `zarurat ke hisaab se`), integer amounts only.
  - `dates.py`: `parse_dates(text, *, reference, date_order)`: day-month-year and month-day-year names in English and Hindi, ISO dates, numeric dates with the deal's order, both readings (`ambiguous_order`, rule `order_date`) when the order is unknown and both are valid, relative dates (`rel_date`), a day with no month (`partial_date`), and month plus day with no year taking the next occurrence on or after the reference (including 29 Feb). Impossible dates are not matches.
  - `percent.py`: `parse_percentages` in basis points (`50%`, `half`, `aadha`, `adha`, Hindi forms).
  - `payment.py`: `parse_payment_phrases`: net days (`30 days after delivery`, `30 din baad`, `net 30`), on and after delivery, on completion, instalments, advance, and vague "later" phrases. Overlaps resolve by priority, so "30 days after delivery" is one net-days match.
  - `penalty.py`: `parse_penalty_phrases`: per day, late fee, penalty, deduction. The word "fine" is deliberately not a penalty cue.
  - `__init__.py`: the public API and the `PARSERS` registry.
- `packages/intelligence/playbooks.py`: `load_playbook(path)`, `load_all(directory)`, `Playbook`, `Term`, `AmbiguityRule`, `LegalHint`, `PlaybookError(message, line)`.
  - Loading: YAML is read through the node tree, so every error names its line. Only plain YAML types are allowed (code tags are refused), keys are checked for duplicates, and unknown fields are rejected.
  - Rules enforced: weights of required terms sum to 100; non-required terms have weight 0; term types; registered parser names; `ambiguity`, `pairs_with`, `handshake_questions` (3 or 4) and `term_missing` references exist; model aliases are unique across terms; every user-facing text has English and Hindi.
  - Lookups: `term(key)`, `required_keys`, `rule(id)`, and `key_for_alias(alias)` (I-02). `ack_window` is optional and defaults to 5. Ambiguity patterns are literal words, not regular expressions.
- `playbooks/supply_order.yaml` and `playbooks/freelance.yaml`: the two MVP playbooks exactly as the documented tables (keys, weights 10/10/10/15/10/15/15/15 and 10/20/15/15/15/10/5/10, types, ask order, pairs, ambiguity rules, handshake questions), with `cues` (I-14), `model_aliases` (I-02) and Hindi drafts. Hindi text and legal hints still need review (Q-17, Q-02 to Q-07). The quantity term's cues double as the unit words that deal type counts in.
- `packages/intelligence/extract.py`: `extract_terms(messages, playbook, *, me_id, counterparty_id, date_order, eligible_ids=None, reference_date=None) -> list[ProposedTerm]`, one per playbook term in playbook order.
  - How a term collects: driven by the playbook's data, not its key (see the module docstring). A term with `quantities` and type quantity counts units named in its cues. Type money with `amounts` is the price. A term with the `payment` parser owns clauses that contain its cue words and builds a `PaymentValue`. A type date term takes dates from messages that contain its cue words. A term with `penalty` takes the sentence that holds the phrase. Other text and enum terms take sentences with their cue words. Type party takes the two chosen participants.
  - States: `stated` (one concrete value), `unclear` (only vague values, with `unclear_reason` set to the playbook's rule id), `contradicted` (two or more different concrete values, neither selected, both in `candidates` with their own sources) and `missing`. A vague value followed by a concrete one gives `stated` with the vague message kept as an extra source (I-16).
  - Price: a total equal to quantity x unit price is a consistency check, not a second candidate; a different total is a conflict. A share of a total (`half`, `aadha`) becomes an amount once the total is known, else `half_adv`. A later "sent 48000" with the same amount adds a source and `when="paid"`. Payment statements that do not contradict each other are merged.
  - Sources: only eligible messages from the two parties count; system lines and messages matching the injection patterns never do (I-23). An amount in a currency other than INR sets `needs_review=True` (I-24).
  - Other: a zero quantity is unclear; the reference date defaults to each message's own date; a rule id that the playbook lacks maps to its first rule of the same flag type.
- `eval/__init__.py`, `eval/runner/__init__.py`, `eval/runner/metrics.py`: `precision_recall_f1(gold, proposed)` with a per-key breakdown. Missing gold terms do not count for recall; a value proposed for one hurts precision; nothing proposed gives all zeros.
- `tests/phase_03/test_parser_fuzz.py`: 1,500 random documents through every parser (no exceptions; spans index the original text) and pathological inputs under 5 s.

### Modified
- `DOCS/TECHNICAL.md` (Playbooks, section 1): the format block and rules now list `ack_window`, `cues`, `model_aliases`, `when.term_missing`, and the validation rules the loader enforces.
- `tests/phase_03/test_playbook_loader.py`: unknown top-level field; alias already used; unknown `term_missing`; parsers that are not a list; bad `ask_order`; missing `cues.en`; duplicate YAML key; empty file; the line number in the error text; `KeyError` for an unknown key; duplicate playbook keys; legal-hint conditions; `ack_window` default.
- `tests/phase_03/test_shipped_playbooks.py`: load from the folder; template sets; registered parsers; hint keywords and conditions.
- `tests/phase_03/test_normalize_rules.py`: spans through collapsed whitespace and Kannada digits; trimming; composed versus decomposed forms.
- `tests/phase_03/test_amounts.py`: the tilde in the span; digits that look like ranges; cue before a unit, month or duration; extra units; long digit runs; per-time amounts; percentages; trailing full stop; huge numbers; Hindi number words.
- `tests/phase_03/test_dates.py`: ISO; ordinal with month; year rollover; 29 Feb; month-first and day-first agree; two dates; month words inside other words; spans; same day and month numbers.
- `tests/phase_03/test_quantities.py`: zero and decimals; playbook units; dozen without a unit; spans.
- `tests/phase_03/test_percent_payment_penalty.py`: decimal percentage; net days beat after-delivery; on completion and Hindi delivery; "fine" is not a penalty.
- `tests/phase_03/test_extract_edge_cases.py`: foreign currency review; zero quantity; year rollover; explicit reference date; eligible ids; context senders and system lines; merging and conflicting balance statements; penalty conflict versus elaboration; parties; playbook order and valid source spans; Devanagari digits; playbook pattern rules for vague text; the freelance date rule fallback; injection patterns.

---

## 2026-10-25 18:19 +05:30 — Phase 4: Flags, Evidence Strength score and suggestions

Implemented PHASES.md Phase 4 (tasks 1 to 8). Not executed or verified.

### Added
- `packages/contracts/formatting.py`: `format_inr(paise)` (Indian grouping, paise shown only when not zero, rejects negatives, floats and non-ASCII digits) and `format_date(date_or_iso, lang)` for `en` and `hi` (I-17).
- `packages/intelligence/templates.py`: the templates folder, a cached YAML loader and `TemplateMissing(key, tone, lang)`.
- `packages/intelligence/score.py`: `ScoreInput`, `compute_score(inputs, playbook)` (0.4 present + 0.3 clear + 0.3 acknowledged, exact `Decimal`, rounded half up, one row per required term, the three counts), the shared `factor` and `ScoreDelta(before, after)` with `.delta` (FR-SCO-003 triggers themselves are Phase 9).
- `packages/intelligence/ack.py`: `acknowledged_keys(terms, messages, *, me_id, counterparty_id, window=5)`: an agreement word (negations such as "not ok" do not count) or a payment of the same amount from the other party within the next `window` messages; party terms are acknowledged once both people have written.
- `packages/intelligence/flags.py`: `build_flags(terms, playbook, messages, *, me_id, counterparty_id, names=None)`.
  - **Unclear terms:** AMBIGUOUS_DATE, AMBIGUOUS_AMOUNT, VAGUE_QUANTITY and VAGUE_PAYMENT, with the playbook rule's own reason; an unclear term whose reason has no playbook rule becomes NEEDS_REVIEW.
  - **Other flags:**
    - MISSING_TERM for required terms only;
    - CONTRADICTION naming every value with its message number;
    - NEEDS_REVIEW;
    - UNACKNOWLEDGED, naming who mentioned it;
    - REGISTRATION_HINT from legal-hint keywords or a missing named term, citing the matching message.
  - Every flag has English and Hindi reasons, and only MISSING_TERM and hints may have no source.
- `packages/intelligence/suggest.py`: `rank_gaps` (conflict first, then weight x (1 - factor) descending, then ask order; I-05), `choose_targets` (top gap plus one `pairs_with` partner that is also a gap), `load_templates` and `build_suggestion`.
  - **Unknown slots:** an unknown fact renders as a bracketed label (`[delivery date]`, `[balance]`) and is listed in `needs_user_input` by term key.
  - **Balance:** computed as total minus advance.
  - **Fallback:** a missing pair template falls back to the top target's own template.
  - **Nothing sends:** the result is plain data.
- `playbooks/templates/{en,hi}/flags.yaml`, `supply_order.suggest.yaml` and `freelance.suggest.yaml`: casual, polite and firm text for every required term and every pair, in English and Hindi. The Hindi text is a draft (Q-17). The firm tone has no threatening words, and there is no literal rupee sign before a money slot (I-18).

### Modified
- `packages/contracts/__init__.py`: `Suggestion.needs_user_input` is now a list of term keys (it was a boolean).
- `packages/intelligence/extract.py`: a vague promise to pay ("will pay soon") that has no cue word now becomes an unclear `vague_pay` candidate of the last payment term, so VAGUE_PAYMENT can be raised for it.
- Tests in `tests/phase_04/`:
  - `test_formatting.py`: bool and float rejected; all 24 month names;
  - `test_flags.py`: Hindi and display names; keyword hint cites its message; unknown unclear reason;
  - `test_score.py`: delta, row order, duplicate inputs;
  - `test_suggestion_text.py`: pair fallback, `TemplateMissing`, bracketed balance in both languages, no Latin words in Hindi, the same facts in all tones;
  - `test_acknowledgement.py`: system lines and third senders do not acknowledge.

---

## 2026-10-25 18:46 +05:30 — Phase 5: Vault, human confirmation and versions

Implemented PHASES.md Phase 5 (tasks 1 to 12). Not executed or verified. Needs `sqlalchemy`, `alembic`, `cryptography` and `argon2-cffi` (listed for Phase 0, which is not built yet). Phases 6 and 7, which were also requested, have not been started.

### Added
- `packages/vault/crypto.py`: `KdfParams`, `DEFAULT_KDF` (placeholder cost, Q-23), Argon2id key derivation, AES-GCM `seal`/`open_`, and the recovery key (160 random bits, 32 base32 characters in groups of four; case, spaces and dashes are ignored).
- `packages/vault/errors.py`: `WrongPassphrase`, `VaultLocked`, `TermNotConfirmable(key, reason)`, `NothingToVersion`, `SelfCheckFailed(results)`.
- `packages/vault/faults.py`: `inject(point)`, `check(point)`, `InjectedFault`; inactive unless a test enters `inject`.
- `packages/vault/migrate.py`, `alembic.ini`, `migrations/env.py` and `migrations/versions/0001_initial.py`: `upgrade(url)` and the CLI command `alembic -c packages/vault/alembic.ini -x url=sqlite:///<path> upgrade head`.
  - **Schema:** every MVP entity table.
  - **Triggers:** `<table>_no_update` and `<table>_no_delete` on the ten insert-only tables, written as raw SQL in the migration.
  - **Phase 6 and 7:** the `recaps`, `confirmations` and `receipts` tables exist but are unused until then.
- `packages/vault/vault.py` and `__init__.py`: the `Vault` class.
  - **Keys:** a random vault data key is wrapped by the passphrase and, separately, by the recovery key, each with its own Argon2id salt. The KDF cost is read from the header (`vault.json`). `create`, `unlock`, `lock`, `change_passphrase`, `kdf_params`.
  - **Encryption:** each deal has its own random key, wrapped by the vault key. Sender names, text, file names, term values, versions and audit details are AES-GCM blobs; only ids, sequence numbers, hashes and states are readable columns. Database is SQLite in WAL mode.
  - **Import:** `commit_import(draft, *, export_bytes, file_name, media, playbook_version=1)` runs in one transaction.
    - It stores the import record, message leaves (`0x10`) in order, encrypted evidence files by digest (stored once), audio as a `not_transcribed` voice note plus a `0x11` leaf, other media as `0x14` leaves, and an `import` audit event.
    - A message that names a media file gets its `attachment_hash`.
    - A second import into the same deal continues `seq` and gets its own batch id.
    - On any failure the transaction rolls back and new evidence files are removed.
  - **Terms:** `save_proposals`, `proposals`, `agreed_terms`, `confirm_term`, `correct_term` (origin `user`), `reject_term`, `acknowledge`. Only a stated proposal can be confirmed as it is; unclear, contradicted and missing terms need an explicit value. Each action writes an audit row with the old and new values and no message text.
  - **Versions:** `create_version` (refused with nothing confirmed; one `0x15` leaf per confirmed term; terms sorted by key; digest, Merkle root and chain link from `packages.integrity`), `versions`, `diff_versions` (`no_change`, `changed`, `added`, `removed`), `record_score`, `audit_events`, `deals`, `participants`, `messages`, `import_record`, `voice_notes`, `leaves`, `evidence_path`.
  - **Checks and deletion:** `self_check()` runs the integrity check, the trigger list, an insert-only probe on a temporary table, and a decrypt-and-hash of every evidence file. `delete_deal` removes the deal key, evidence files nobody else uses and the deal's rows where allowed, with one content-free audit event.
  - **Logging:** event names and counts only; the SQLAlchemy engine logger is held at WARNING.

### Decisions to note
- **Evidence encryption:** evidence files are encrypted with the vault data key, with the digest as associated data, not the deal id. The same file in two deals is therefore stored once and survives deleting one of them; the deal key shreds everything else.
- **Playbook version:** the vault cannot import the intelligence package, so the playbook version in a terms set is a `commit_import` argument (default 1).
- **Audit and shredding:** the content-free `delete_deal` event is encrypted with the vault key so it stays readable; a deleted deal's other audit events are encrypted with its deal key and drop out of `audit_events`.

### Tests (`tests/phase_05/`, added to the existing files)
- `test_vault_crypto.py`: locked vault refuses everything, locking twice, an unlock needs a secret, the recovery-key format.
- `test_import_commit.py`: a second import into the same deal, attachment hash links, stored participants.
- `test_human_confirmation.py`: origin kept when an explicit value equals the proposal; dict values validated; acknowledge needs an agreed term; unknown key; a chosen conflict candidate keeps its sources; audit per deal.
- `test_versions.py`: a correction after a version changes only the next one, hashed fields only, per-deal numbering, an unknown version in a diff.
- `test_self_check_and_delete.py`: delete survives a reopen, unknown deal, shared evidence survives, strict self-check raises with all results.

---

## 2026-10-25 18:59 +05:30 — Phase 6: Recap and echo-code confirmation

Implemented PHASES.md Phase 6 (tasks 1 to 7, 5a). Not executed or verified.

### Added
- `packages/ingest/recap.py`: `build_recap(terms, playbook, language, other_name, *, deal_id, version_n) -> RecapDraft` and `build_whatsapp_message(recap)`.
  - **Lines:** driven by the recap template file. A line needs all its terms. Amounts use `format_inr`, dates `format_date` (I-07), bullets are `• `. The variant of a line (advance received or due, balance on or after delivery or on a date, price per item or total) comes from the term's value; a balance with no amount reads "Balance due on delivery".
  - **Omissions:** a line with a missing or unusable term is left out, with its terms in `omitted_terms` as `not_confirmed` or `incomplete_line`. Unconfirmed required terms are listed; optional terms (GST) are not.
  - **Languages:** English and Hindi; any other language is a `ValueError`. The draft carries the closing line with a `{code}` slot and computes no hash.
- `packages/contracts/templates.py`: the shared template loader (`TEMPLATES_DIR`, `load_yaml`). `packages/intelligence/templates.py` now wraps it, so ingest, intelligence and the vault read templates the same way.
- `playbooks/templates/{en,hi}/{supply_order,freelance}.recap.yaml` and `replies.yaml`: recap lines, greeting and closing (`CONFIRM` and the code stay Latin in Hindi), and the four failure messages plus the success message. Hindi is a draft (Q-17).
- In `packages/vault/vault.py`:
  - `create_recap(deal_id, version_n, draft) -> Recap`: `recap_hash` over `deal_id`, `version_n`, `language`, `lines` and `body_text` only (D1), the echo code from it, and `text` = body plus the closing line with the code. The version must exist (`VersionNotConfirmable`). Writes a `sent` confirmation row and a `send_recap` audit event.
  - `approve_recap(recap_id)`: the user's own approval, as a confirmation row for party `me` (audit `approve_recap`).
  - `check_reply(recap_id, pasted_text, sender=None) -> ConfirmationResult`:
    - **Parsing:** headers (Android or iPhone) are parsed with a small pattern in the vault, because the vault may not import the ingest package. A paste without a header needs `sender` (else `ValueError`) and is marked `sender_entered_by_user`.
    - **Message choice and failure order:** the last message from the counterparty containing `CONFIRM` is used. Failures are checked in this order: `no_code`, `wrong_sender`, `stale_code`, `code_mismatch`. Only the deal's most recent recap can be confirmed (I-20); an older recap, or an older recap's code, gives `stale_code`. The code is read with the Phase 1 `extract_code` (look-alike mapping on the code only, I-08).
    - **Stored result:** every attempt is stored as a confirmation row. Only a success writes a `0x22` leaf (with the fields of INTEGRITY_SPEC 4.2) and marks every term of the recap's version `acknowledged_by_other` (5a). Audit `check_reply`.
    - **Result shape:** a failure is a result with `message_en` and `message_hi`, never an exception.
  - `confirmations(recap_id)`, `version_confirmed(deal_id, n)` (true only when one recap of version `n` has both the user's approval and a verified reply).
- `RecapNotFound` and `VersionNotConfirmable` (both `KeyError`) in `packages/vault/errors.py`.

### Modified
- `packages/contracts/__init__.py`: `RecapDraft.closing` and the `ConfirmationResult` model.
- `packages/vault/migrations/versions/0001_initial.py`: the `confirmations` table has a clear `party` column (the migration is not released yet, so it was edited in place).
- `packages/vault/vault.py`: `_add_leaf` returns the new leaf id; `acknowledge` shares a helper with the reply check.
- Tests in `tests/phase_06/`:
  - `test_recap_builder.py`: total-price line, balance without an amount, unusable value, unconfirmed required terms, optional terms never listed, closing line, per-line dates;
  - `test_reply_check.py`: unknown recap, iPhone header, look-alike letters, Hindi messages, sender case and spaces, acknowledgement on success only;
  - `test_version_confirmation.py`: the sent then confirmed states, a confirmation never counts for another recap.

### Decisions to note
- `reply_ts` in a confirmation leaf is the time the reply was checked, because a pasted header carries no UTC offset.
- The vault duplicates a short header pattern instead of using the Phase 2 parser, to keep the documented dependency rule.

---

## 2026-10-25 19:05 +05:30 — Phase 7: Receipt, bundle, verifiers and tamper tests

Implemented PHASES.md Phase 7 (tasks 1 to 6; task 7, publishing the page hash, is a release step). Not executed or verified. **Generated files are not committed yet:** run `python scripts/build_verify_page.py` once to write `apps/verify/verify.html`, and `python scripts/make_tamper_fixtures.py` once to write `test-vectors/integrity/tamper/` (the static-page, JavaScript and fixture tests need them).

### Added
- `packages/integrity/verify.py`: `verify_bundle(path_or_bytes) -> VerifyResult`, `BundleFormatError`, `UnsupportedSpecVersion`, and `python -m packages.integrity.verify <bundle.zip>`.
  - **Checks:** `spec_version` (the version is supported and the receipt hash matches its body), `leaves`, `merkle_root`, `chain`, `version_roots`, `import_record`, `timestamps`, `anchor`.
  - **Leaves:** each leaf is recomputed from what the bundle discloses (payload, or media file, with the salt); a leaf with nothing disclosed is taken as given. The Merkle root is rebuilt from the recomputed hashes (I-21). A gap or a misplaced row names the first row that does not fit.
  - **Chain:** digests and links are recomputed and compared with both `chain.json` and the receipt body; a version in the body but missing from `chain.json` (or the reverse) fails. Each version root is checked against the leaf prefix it names.
  - **First difference:** the first differing item is chosen in this order: lowest leaf, lowest chain version, lowest version-root version, import record, root only, receipt.
  - **Timestamps and anchor:** an inconsistent time order is a warning, never ALTERED by itself. An anchor is reported but not checked offline. Unknown extra members are warnings.
  - **Errors:** an unreadable file raises `BundleFormatError("This file is not a VeriDoc receipt bundle.")`. An unknown spec version raises `UnsupportedSpecVersion` and is not called ALTERED.
- `apps/verify/verify.mjs`: the same verifier in JavaScript, `async verifyBundle(zipBytes)`, with a small zip reader (stored and deflate entries through `DecompressionStream`). No network.
- `apps/verify/verify.template.html` and `scripts/build_verify_page.py`:
  - The build script inlines `integrity.mjs` and `verify.mjs` into the one-file page `apps/verify/verify.html` (I-22), and `--check` fails when the page is stale.
  - The script prints the page's SHA-256 for the release notes.
  - The page has a drop zone, one line per check with a symbol and a word, `✓ UNCHANGED since recording` or `⚠ ALTERED after recording`, the first differing item, and the limit text always visible.
  - Results are written as text nodes, never as HTML, and the page has no network API.
- `scripts/make_tamper_fixtures.py`: writes `unchanged.zip`, the eight tamper zips (seven cases plus the import record) and `expected.json` to `test-vectors/integrity/tamper/`, with fixed zip timestamps; `--check` compares. Bundles come from `tests/phase_07/bundle_builder.py`.
- In the vault: `build_receipt(deal_id) -> Receipt(body, receipt_hash)` and `export_bundle(deal_id, out_dir, include_media=False) -> Path`.
  - **Receipt:** the body has the INTEGRITY_SPEC section 9 fields plus `import_record_hash`; it is stored in `receipts` with a `receipt` audit event.
  - **Bundle:** every leaf disclosed, in the Appendix D format. It is written atomically as an unencrypted zip whose README states the limit text and that the file is not encrypted. `export` is audited.

### Modified
- `packages/contracts/__init__.py`: the first-difference kind `receipt`.
- `packages/vault/vault.py` and the initial migration: a version stores `leaf_count`, the number of leaves its root covers; `VersionRecord` has the field.
- Tests in `tests/phase_07/`:
  - `test_python_verifier.py`: receipt hash edit, a version root that does not match, a chain entry that disagrees with the receipt, an extra version, a missing import record, a malformed leaf row, a misplaced row, the command line;
  - `test_receipt.py`: the leaf count a version covers, an empty chain;
  - `test_bundle.py`: `chain.json` and the import record, the media member, a replaced exported audio file, the README;
  - `test_verify_page_static.py`: text nodes only, a drop zone, the verifier and primitives are inlined.

---

## 2026-10-25 19:11 +05:30 — Phase 8: Local open-source model with deterministic validation

Implemented PHASES.md Phase 8 (tasks 1 to 9). Not executed or verified. No model file is bundled and none was downloaded; the real-model smoke test (marker `model`) needs `VERIDOC_MODEL_PATH`, a manifest entry and the optional `llama-cpp-python` extra. The model and its licence are still open questions (Q-13, Q-46). There is no fine-tuning (R-03).

### Added (`packages/intelligence/model/`)
- `port.py` (`ModelRunner.generate(system, data_block, schema, timeout_s)`), `fake.py` (`FakeModelRunner(response, delay_s=0.0, error=None)` recording `calls`), `llama_cpp.py` (`LlamaCppRunner(model_path)`: CPU, temperature 0, JSON-schema grammar; the library is imported only when the runner is built).
- `prompt.py`: `SYSTEM_INSTRUCTION`, `build_prompt(messages, playbook, fence_token=None, eligible_ids=None) -> Prompt(system, data_block, fence_token, schema)`.
  - **System text:** fixed code plus the playbook's term keys; never any chat text.
  - **Data block:** a JSON array of `{seq, sender, text}` between two copies of a random per-call fence token. A token that appears in any message is replaced. System lines are never sent.
  - **Schema:** `additionalProperties: false`, keys limited to the playbook, states `stated`, `unclear` and `contradicted`.
- `output.py`: `parse_model_output(raw, playbook, messages) -> (list[ModelTerm], list[OutputProblem])`.
  - **No exceptions:** invalid JSON is a counted problem, never an exception.
  - **Keys and fields:** model keys map to playbook keys through the aliases (I-02); an unknown key is dropped; extra fields are ignored; a bad state or bad source positions make the term `needs_review`; confidence is clamped to 0 to 1.
  - **Values:** normalised by the playbook term's type. Money (`₹60,000`, `50k`, `1.5 lakh`) goes to paise. A term with the `payment` parser takes an amount or a timing word. Dates take `YYYY-MM-DD`, or `MM-DD` which becomes `--MM-DD`. Counts must be whole numbers. A value that cannot be read leaves the term `needs_review` with no value.
- `grounding.py`: `ground_terms(model_terms, messages, rule_terms, *, me_id, counterparty_id, eligible_ids=None) -> (accepted, failures)`.
  - **Failure reasons, checked in this order:** `unknown_source`, `ineligible_source`, `injection_source` (every usable source matches the shared injection patterns), `quote_not_found` (compared after normalisation), `value_not_derivable`.
  - **Value check:** the value must be readable from the quote by the rules parsers, or equal a rules value that cites the same message. Party names must be the two chosen parties.
  - **Failures are returned so they can be counted.**
- `refine.py`: `refine_terms(...) -> RefineResult(terms, grounding_failures, dropped, used_model, error)`.
  - **Failure handling:** the model runs in a helper thread so the call returns within `timeout_s` even if the model keeps going. A timeout, an exception or invalid output leaves the rules result with `error` set to `timeout`, `runner_error` or `invalid_output`. Log lines carry codes only. `runner=None` returns the rules result.
  - **Comparison (FR-AIS-004):**
    - Agreement gives origin `both`.
    - A disagreement gives `needs_review`, no selected value, and both values as candidates.
    - A grounded term where the rules found nothing usable gives origin `ai` with `needs_review`.
    - A conflict in the rules is never overridden.
    - Only the first grounded model term per key counts, and a model that says "unclear" proposes nothing.
- `models.py`: `verify_model_file(path, entry)` (size, then streamed SHA-256; a missing file is `False`), `select_tier(ram_gb, has_avx2, thresholds)` (no AVX2 caps at `low`), `ModelStatus`, `analysis_mode(safe_mode_switch, status)` with reasons `switch`, `model_missing`, `hash_mismatch`, `load_failed`, `low_hardware`. The switch is an argument, so each call sees the current value.
- `eval/runner/metrics.py`: `ai_contribution(gold, rules_only, rules_and_ai)` for the trust report: the scores of the rules alone, of rules plus model, and the difference.

### Modified (tests in `tests/phase_08/`)
- `test_output_parsing.py`: money forms, timing words, payment amounts, whole-number counts, party and text values, entries that are not objects, bad dates.
- `test_grounding.py`: dates, quantities, party names, one clean source among injected ones, an unreadable value, `eligible_ids`.
- `test_refine_compare.py`: an unsure model, a rules conflict is kept, first term per key, the dropped count, an AI proposal for a vague rules term, `ai_contribution`.
- `test_models_and_safe_mode.py`: size mismatch, an entry without a hash, an unchecked model, the switch read on every call.
- `test_prompt.py`: playbook keys in the system text, the fence token, system lines never sent, the schema.
- `test_refine_failures.py`: an answer in time is used, the invalid-output count, the prompt the runner received.
