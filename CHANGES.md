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
