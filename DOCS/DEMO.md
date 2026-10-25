# VeriDoc Demo

Demo script, demo-day runbook and judge Q&A.

## Contents

- [Demo Script](#demo-script)
- [Demo Day Runbook](#demo-day-runbook)
- [Judge Q&A](#judge-qa)

---

## Demo Script

This is the four-minute live demo, the sample chats it needs, the fallback plan and the recorded backup. It follows the flow Handshake, Recap, Receipt. Timings are plans, not measurements.

Last updated: 2026-10-25
Status: Draft v1

### 1. Roles and setup

| Role | Person |
|---|---|
| Presenter (acts as Raju) | TBD |
| Second person (acts as Meena, answers on a phone) | TBD |
| Operator (backup laptop, video) | TBD |

Setup checklist:
1. The USB 3 stick holds the release build. A second laptop (not a development machine) is used for the demo.
2. A phone with WhatsApp holds a prepared chat, so the recap can be shown arriving and "CONFIRM <code>" can be sent. If the phone fails, use the sample reply text.
3. The vault already has a passphrase set. The recovery key is printed and kept aside.
4. Wi-Fi is on at the start, to be turned off on stage.
5. Samples loaded: clean, ambiguous, contradictory, and one with a voice note.
6. Hindi fonts verified on the demo laptop.
7. A tampered copy of the receipt bundle is prepared in advance as a backup for the tamper test.

### 2. Sample chats needed

| Sample | Purpose | Content summary |
|---|---|---|
| Clean | Shows a high score and no flags | Raju and Meena (or another pair) agree on every term with fixed dates and amounts |
| Ambiguous (main demo) | Shows flags and a suggestion | 200 shirts, ₹480 each, ₹48,000 advance, "delivery next week", no final payment, no late penalty |
| Contradictory | Shows the Conflict flag | Price ₹50,000 in one message and ₹45,000 in another |
| Voice sample | Shows text versus voice contradiction and play the moment | Text says 15 Nov; a voice note says 22 Nov |
| Hinglish sample | Shows rules for number words | Includes "pachaas hazaar" and "aadha advance" |

All samples are synthetic. Each has a gold label file in `eval/labels/` (Area 2) and the chat file is provided by Area 1 (Hardik).

### 3. The four-minute script

| Time | Step | What to do and say | Screen |
|---|---|---|---|
| 0:00 to 0:25 | Problem | Show the ambiguous chat in WhatsApp. "A real deal: price in one message, delivery 'next week', balance never mentioned. This is how most small deals work." | Phone, then S2 |
| 0:25 to 0:40 | Offline proof | Turn Wi-Fi off. Plug in the stick, double-click START. "Everything runs on this laptop." Point to the Offline mode indicator. | S1 |
| 0:40 to 1:30 | Live analysis | Load the ambiguous sample. Terms appear with sources. Open delivery in S4: the reason "next week could be 5 to 12 days away". Show the voice note: text says 15 Nov, voice says 22 Nov, press Play the moment. Show the score. | S2, S3, S4 |
| 1:30 to 1:55 | Next message | Show the suggested message, switch tone, press Use this. Import the reply (or add it in the simulator). The score rises. "Others explain the dispute after it happens. We help you avoid it while you are still chatting." | S3 |
| 1:55 to 2:20 | Blind Handshake (first to drop) | Handover mode (demo mode): the presenter answers and seals first, then the second person answers on the same screen, then reveal. Mention that real use is reply mode over WhatsApp. Show a delivery date mismatch. If time is short, skip it. | S5 |
| 2:20 to 3:00 | Recap and confirm | Generate the Hindi recap. Copy the WhatsApp message with the code. The second person replies "CONFIRM <code>" on the phone. Paste the reply. Show Confirmed. | S6, S12 |
| 3:00 to 3:50 | Receipt and tamper test | Open the receipt: chain, root, device-clock time. Open the verify page: UNCHANGED with each check. Change one character in the exported chat. Verify again: ALTERED, naming message #7. Read the limit line aloud. | S8, S9 |
| 3:50 to 4:00 | Close | "Handshake, Recap, Receipt. A promise made in chat should be a promise you can prove." | S1 |

The dispute pack (S10) is mentioned in one sentence ("one export for a lawyer or the MSME Facilitation Council") and shown only if time allows.

### 4. Success criteria

**Numbers on screen.** Every score and metric shown in the demo comes from the real formula (PRD FR-SCO-001) or from a named trust report. The values in the wireframes (for example 68) are illustrative only and must not be spoken as results. Rehearse with the actual computed score for the chosen sample.


See PRD section 15. In short: runs offline on a second laptop; flags shown; score rises; Hindi recap confirmed; tamper test names the changed message; within about four minutes.

### 5. Fallback plan

| Failure | Fallback |
|---|---|
| AI model slow or failing | Keep going: rules results appear first. Switch safe mode on if needed. Say so. |
| Voice transcription slow | Use the pre-imported voice sample; transcription runs at import, not live |
| Stick not recognised or antivirus blocks | Use the laptop install of the same build, or the recorded video |
| Phone or WhatsApp fails | Paste the prepared reply text "CONFIRM <code>" from the second laptop notes |
| Wrong code or recap changed | Show the "not confirmed" state, then regenerate; it is also a good demo of stale codes |
| Hindi font problem | Switch the recap to English |
| Verify page fails to open | Use the pre-opened tab on the backup laptop |
| Total failure | Play the recorded backup and narrate |

### 6. Recorded backup

1. Record the full flow on the demo laptop with the network off, with voice-over, within four minutes.
2. Record a second short clip of the tamper test alone.
3. Keep both on the stick, on the laptop and on a phone. Name the files with the build commit.
4. Re-record if the UI changes.
5. Narration text matches this script and uses only measured numbers from a named trust report.

### 7. Questions to expect

See [JUDGE_QA](#judge-qa).

---

## Demo Day Runbook

This runbook is the plan for the day of the demo: the timeline, who does what, the equipment list, the checks to run, and what to do when something fails. The demo itself is scripted in [DEMO_SCRIPT](#demo-script) and the fallback plan is there too; this file covers the surrounding day. Names, times and the venue are `TBD` (OPEN_QUESTIONS Q-10).

Last updated: 2026-10-25
Status: Draft v1

### 1. Roles

| Role | Person | Duty |
|---|---|---|
| Presenter (acts as Raju) | TBD | Speaks and drives the demo laptop |
| Second person (acts as Meena) | TBD | Replies on the phone; answers judge questions on the AI |
| Operator | TBD | Backup laptop, recorded video, timer, networking |
| Q&A lead | TBD | Answers legal and integrity questions using [JUDGE_QA](#judge-qa) |

### 2. Timeline

All times are `TBD` and set once the event schedule is known.

| When | What |
|---|---|
| Two days before | Build the demo stick from the tagged `v0.4-phase4` commit; run the full RELEASE_CHECKLIST |
| Day before | Final rehearsal on the demo laptop and the backup laptop; charge everything; print the recovery key and the one-page cheat sheet |
| Morning | Pack the equipment list; test the stick on the demo laptop once more |
| Arrival | Find the power, the table and the screen; set up the laptops; do the pre-flight checks (section 4) |
| 30 minutes before slot | Close all other apps; do the pre-flight again; open the tabs |
| Slot | Run the four-minute script |
| After | Q&A; collect feedback; note questions in OPEN_QUESTIONS |

### 3. Equipment list

- [ ] Demo laptop (not a development machine) with charger
- [ ] Backup laptop with the same build and charger
- [ ] Two USB 3 sticks (exFAT) with the same tagged build, and one spare
- [ ] Phone with WhatsApp and a prepared chat, and the second person's phone
- [ ] A second phone with the recorded backup video, and the video on both laptops
- [ ] Printed recovery key and passphrase card (kept apart from the sticks)
- [ ] HDMI, USB-C and display adapters; extension lead
- [ ] A phone hotspot (not used by the app; for chat messages on the phone only)
- [ ] The tampered receipt bundle prepared for the backup tamper test
- [ ] Printed one-page cheat sheet: script timings and the limits wording
- [ ] Water and a charger for the phones

### 4. Pre-flight checklist (run on each laptop)

- [ ] Battery above 80% and plugged in; power saving off; notifications off
- [ ] Wi-Fi off (the demo proves offline); Bluetooth off
- [ ] Stick plugged in; the launcher starts the app
- [ ] The UI is usable in under 15 seconds from the stick (target; note the actual time)
- [ ] The vault unlocks with the passphrase
- [ ] The model hash check shows "Hash verified" in settings (or safe mode is deliberately on)
- [ ] Samples load: clean, ambiguous, contradictory, voice
- [ ] Play the moment plays the voice clip
- [ ] The Hindi recap shows Devanagari correctly
- [ ] The WhatsApp phone can receive the recap text and send `CONFIRM <code>`
- [ ] The verify page opens by double-click and the tamper test turns UNCHANGED into ALTERED
- [ ] The recorded video plays on the demo laptop and on the phone
- [ ] Screen scaling and font sizes are readable from the back of the room

### 5. If something fails

The full table is in [DEMO_SCRIPT](#demo-script) section 5. The short rules:
1. Do not apologise at length. Say what happened in one sentence and switch.
2. Keep the time: the operator signals at 2:00 and 3:00.
3. AI slow: carry on with rules results and say the AI refines in the background.
4. Phone fails: paste the prepared reply text.
5. Stick or antivirus problem: switch to the backup laptop, then to the video.
6. Total failure: play the recorded video and narrate it. Never improvise a claim.
7. Do not quote a number that is not in the trust report. If asked for one, say it is a target until measured.

### 6. After the demo

- [ ] Write down every judge question and who answered it
- [ ] Add new questions to JUDGE_QA and any open item to OPEN_QUESTIONS
- [ ] Back up the demo stick image
- [ ] Short team retro: what to keep, what to change

---

## Judge Q&A

Likely questions from judges with short, honest answers. Numbers are quoted only from a trust report that was actually run; until then they are targets.

Last updated: 2026-10-25
Status: Draft v1

### Product and problem

**Why not just use ChatGPT or Claude?**
A chatbot explains a chat once. VeriDoc keeps a live structured record where each term links to its source message or voice-note time range. It warns during the chat, suggests the next message, collects confirmation from both sides, and produces a record anyone can check. It also runs offline, so business chats stay on the device.

**Who is it for?**
Small suppliers and vendors who deal over chat: tailors, printers, freelancers, tutors, contractors, caterers, photographers, and people who lend money informally.

**Why LS-06?**
Provable terms come before every other right. If a deal is not recorded clearly, payment, delivery and dispute rights are hard to enforce later. LS-06 sits upstream of the MSME payment and notice problems.

**What does it do that is not just a template generator?**
It does not start from a template. It starts from what the parties actually said, shows what is missing, and builds the recap from confirmed terms.

### Legal

**Is this legal advice?**
No. It is a drafting and record-keeping aid, and it says so on screen. A lawyer must confirm every statement about Indian law.

**Is a chat agreement valid?**
Some agreements made over chat may be valid contracts. We do not decide that; we make the terms and the evidence clearer. Confirm with a lawyer.

**Do you replace a registered or stamped agreement?**
No. Some deals may need a written, stamped or registered document. The playbook tells the user to ask a lawyer.

**What is the Section 63 certificate?**
An unsigned draft certificate for electronic records, included in the dispute pack. The person responsible for the device must complete it. A lawyer must confirm its form and use.

**Will this stand up in court?**
We make no promise. The dispute pack is a court-ready evidence package in the sense of an organised export with a timeline, hashes and a verification guide. Admissibility is for the court.

### Integrity

**What does the hash prove?**
That the record was not changed after it was saved. It does not prove the original chat export was genuine. The product says this on the receipt and verify screens.

**Can it detect fake chats?**
No, and we do not claim it. In P1 it flags integrity red flags such as timestamp order problems; these are warnings, not verdicts.

**What if the device clock is wrong?**
Then the recorded time is wrong. S8 says the time comes from the device. Optional anchoring (P1) gives an independent time.

**Why a salted Merkle tree?**
Salts stop guessing of hidden messages. The tree lets us share only chosen messages later and still verify them against the same root.

**Can the other person fake the confirmation?**
The code is a short binding check on the exact recap, not authentication. The reply is stored as evidence and must come from the counterparty in the chat. It relies on the export being genuine, and we say that.

**Can the record be made impossible to change?**
No. It is tamper-evident: a change after saving is detected, not prevented.

### AI

**Which model do you use? Did you train it?**
We run small open models locally with schema-constrained output. Exact models are chosen after benchmarks (TBD). By default we use the base models. Fine-tuning is an optional later task, and we would claim it only if it beats the base model on our eval set; the comparison goes in the model card.

**What if the AI is wrong?**
The AI only suggests. Every value must appear in a real message or transcript span. If rules and AI disagree, the term is marked needs review. A person confirms every term. Without the model, safe mode runs rules only.

**What about prompt injection in a chat?**
Chat text is treated as data. Output is schema-constrained, values are grounded, and injection tests are part of the eval.

**How accurate is it?**
Our target is at least 90% field-level extraction on our eval set of about 100 chats. The measured number comes from the trust report; we show it by language, including Hinglish and Kannada-English where small models are weaker. Until a report is run, this is a target.

**Does it work in Indian languages?**
English and Hindi recaps in the MVP. Kannada is P1 after native-speaker review. Extraction is tested on Hinglish and Kannada-English chats and Hindi voice notes.

**Does the AI send messages for me?**
No. It suggests; you copy and send it yourself.

### Privacy and security

**Does data leave my laptop?**
Not by default. There is no cloud AI. Optional anchoring sends only a hash. The optional share link sends only ciphertext.

**What about the other person's privacy?**
We process their messages on your device. A lawyer must review data-protection duties (DPDP) before public launch. This is an open item.

**What if the stick is lost?**
The vault is encrypted with a key derived from your passphrase. A recovery key is printed at setup. If both are lost, the data cannot be opened.

### Business and scope

**How will it make money?**
Hypothesis, not validated: free offline individual version, then a paid team tier with sync and optional professional review. See ROADMAP.

**Is the pendrive the product?**
No. It is a delivery vehicle and demo proof. The same build installs on a laptop.

**What did you build for this event?**
All code is new. See PRIOR_WORK for where the design ideas came from.

**What is not built?**
Android app, phone web app, in-person voice sealing, UPI screenshot check, CA countersign, cloud sync, teams and billing, WhatsApp extension. P1 items are listed in the roadmap.

**What did you cut and why?**
Reliability scores, fake-chat detection claims, verdict prediction, a template library, a payment ledger, an interest calculator, notice escalation, fine-tuning claims without an eval gate, and RAG. They cannot be validated, drift into legal practice, or are outside LS-06.

**Will the other party really reply with a code?**
It is one short WhatsApp reply to a friendly message, with no link and no install. The confirmation rate is a metric we will measure in a pilot; we have no number yet.
