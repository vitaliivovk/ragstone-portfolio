# Northwind bot — manual test questions (May 2026 feedback)

## Purpose

This checklist turns internal QA feedback (May 2026) into **repeatable manual tests** for the Northwind Residences Teams assistant. Use it after code or corpus changes to confirm regressions are fixed and UX improvements (clarification gate, answer composer) behave as intended.

**How to use**

1. Open the **Teams dev/test bot** (limited rollout during doc updates — see feedback doc § D2 when available).
2. Run each case in a **fresh thread** unless the case is explicitly multi-turn (same conversation).
3. Compare the bot reply to **Expected answer (acceptance criteria)** below — pass/fail per bullet.
4. Automated eval: **`.cursor/skills/bot-quality-evaluation`** — e.g. `./scripts/bot.sh rag --file logs/client_feedback_golden.txt`  
   Golden one-liners: [`teams-bot/logs/client_feedback_golden.txt`](../../../teams-bot/logs/client_feedback_golden.txt).

**Source docs**

| Doc | Role |
|-----|------|
| This file (`acceptance-criteria.md`) | Reporter issues A1–B5, C4 — manual test cases |
| [CLIENT-FEEDBACK-CORPUS-REMEDIATION.md](../../../pinecone-pipeline/docs/CLIENT-FEEDBACK-CORPUS-REMEDIATION.md) | Corpus excerpts & reindex checklist |
| [CLIENT-FEEDBACK-ARCHITECTURE-CHANGES.md](../../../teams-bot/docs/CLIENT-FEEDBACK-ARCHITECTURE-CHANGES.md) | Clarify gate, topic composer (Wave 3) |

**Important:** Acceptance criteria describe **what the bot should say given current/internal documentation intent** — not legal advice. When corpus is missing or out of product scope, an honest **OUT_OF_SCOPE** / „brak informacji w materiałach” response is acceptable (see A12, A19).

---

## A. Content accuracy (DATA / GENERATION)

### A1

- **Reporter / source:** Katarzyna Słowicka — feedback doc § A1
- **Issue type:** DATA
- **Conversation:**  
  `Jakie warunki egzekucji obowiązują firmę przy składaniu oświadczenia notarialnego — czy obejmują sumę rocznego czynszu plus opłat eksploatacyjnych?`
- **Expected answer (acceptance criteria):**
  - MUST mention that enforcement for the notarial statement is capped at **roczny czynsz + opłaty eksploatacyjne** (or equivalent wording).
  - MUST stay on **najem instytucjonalny / firma / oświadczenie notarialne** — not generic tenant enforcement.
  - MUST NOT omit the cap entirely while only stating „poddanie się egzekucji” without the sum formula.
  - If materials truly lack the cap: MAY state gap explicitly — flag as corpus follow-up (see evidence doc § A1 partial).

### A2

- **Reporter / source:** Katarzyna Słowicka
- **Issue type:** DATA
- **Conversation:**  
  `Czy weryfikacja finansowa obcokrajowców bez numeru PESEL przebiega automatycznie?`
- **Expected answer (acceptance criteria):**
  - MUST address **obcokrajowiec bez PESEL** and **weryfikacja finansowa**.
  - SHOULD describe **automatic** path where policy/the partner verification service applies (per tester expectation), not manual-only.
  - MUST NOT answer only „weryfikacja manualna” without nuance if CONTEXT supports the partner verification service.
  - MAY contrast with PESEL → the partner verification service when both appear in materials.

### A3

- **Reporter / source:** Katarzyna Słowicka; Joanna Pertyk (docx)
- **Issue type:** DATA
- **Conversation:**  
  `Co oznacza brak weryfikacji finansowej — czy bez weryfikacji nie można podpisać umowy — i jaka jest konsekwencja przy negatywnym BIK/KRD oraz negatywnych dochodach (3 miesiące)?`
- **Expected answer (acceptance criteria):**
  - MUST state that **brak weryfikacji** ⇒ **brak możliwości podpisania umowy** (tester rule).
  - MUST cover **negatywny BIK/KRD + negatywne dochody** ⇒ **kaucja 3 miesiące** (or current policy tier), not outdated generic „3 m-ce” as a label for „brak weryfikacji”.
  - MUST NOT equate „Brak weryfikacji” in Procesy slide sense (deposit tier only) with signing allowed.
  - SHOULD separate identity vs financial verification if both appear in CONTEXT.

### A4

- **Reporter / source:** Katarzyna Słowicka
- **Issue type:** DATA
- **Conversation:**  
  `Jaka jest minimalna opłata za wcześniejsze rozwiązanie umowy najmu (czy wynosi co najmniej jeden miesiąc czynszu)?`
- **Expected answer (acceptance criteria):**
  - MUST state **minimum = jeden miesiąc czynszu** (numeric answer prominent if composer active).
  - MUST NOT omit minimum when discussing wcześniejsze rozwiązanie.
  - SHOULD name contract context (porozumienie / przedłużenie) if needed for max cap.

### A5 (multi-turn)

- **Reporter / source:** Katarzyna Słowicka — misroute / vague 24+ month termination
- **Issue type:** RETRIEVAL + clarify (multi-turn repro)
- **Conversation:**
  1. `Jak wygląda wcześniejsze rozwiązanie umowy najmu na okres 24 miesięcy lub dłużej?`
  2. *(If bot asks clarifying questions — answer e.g.:* `Chodzi o przedłużenie umowy najmu instytucjonalnej (W), nie pierwszą umowę I.` *)*
  3. `Jak wygląda wcześniejsze rozwiązanie umowy najmu na okres 24 miesięcy lub dłużej — jakie dokumenty i opłaty obowiązują (bez mylenia z materiałem RE)?`
- **Expected answer (acceptance criteria):**
  - **Turn 1:** SHOULD trigger **clarification** (typ umowy: pierwsza vs przedłużenie; I/W/N/R) OR ask which document family — MUST NOT guess with a long RE-heavy answer.
  - **Turn 3 (final):** MUST cite **przedłużenie / porozumienie** rules, not redirect to unrelated **RE** materials.
  - MUST include **max opłata do czterech miesięcy czynszu** and **min jeden miesiąc** where applicable to ≥24-month extension (per Przedłużenie evidence).
  - MUST NOT lead with Procesy **½ czynszu / max 3×** as the only rule for this scenario.
  - MUST NOT be vague „analiza 36 miesięcy” without concrete caps.

### A6

- **Reporter / source:** Katarzyna Słowicka
- **Issue type:** DATA
- **Conversation:**  
  `Jaka jest wysokość opłaty za wcześniejsze rozwiązanie umowy — czy cztery miesiące czynszu — i jaka jest kwota minimalna (jeden miesiąc czynszu)?`
- **Expected answer (acceptance criteria):**
  - MUST state **cztery miesiące czynszu** as cap where tester scenario applies (≥2y extension path).
  - MUST repeat **minimum jeden miesiąc czynszu**.
  - MUST NOT say **trzy miesiące** as the maximum for that same scenario.
  - Numeric amounts in **first sentence** when composer `numeric_answer_first` applies.

### A7

- **Reporter / source:** Klaudia Konicka
- **Issue type:** DATA
- **Conversation:**  
  `Co oznacza brak weryfikacji przy ustalaniu kaucji i czy nadal obowiązuje kaucja czteromiesięczna?`
- **Expected answer (acceptance criteria):**
  - MUST NOT present outdated pair: **„brak weryfikacji → kaucja 3 mies.”** + **„umowa do 4 miesięcy”** as current policy without qualification.
  - SHOULD align **brak weryfikacji** with **brak podpisania** (see A3).
  - MUST NOT prominently claim **4-miesięczna kaucja** as standard without CONTEXT support.
  - Positive path (+10%) should not be buried below stale Procesy text.

### A8

- **Reporter / source:** Vlad Nikoliuk (May 12); meta-audit
- **Issue type:** DATA (audit)
- **Conversation:**  
  `Gdzie w instrukcjach i prezentacjach opisano zasady weryfikacji finansowej i wysokość kaucji (aktualne procesy)?`
- **Expected answer (acceptance criteria):**
  - SHOULD point to **Instrukcja**, **przykladowe_tresci_maili** (or equivalent indexed paths).
  - SHOULD acknowledge **conflicts** (3 vs 4 months, brak weryfikacji labeling) if present in CONTEXT.
  - MUST NOT assert a single stale rule without noting document family.
  - Pass = helpful pointers; full corpus fix is out of band for bot-only testing.

### A9 (multi-turn)

- **Reporter / source:** Joanna Pertyk — first lease vs extension
- **Issue type:** GENERATION + clarify
- **Conversation:**
  1. `Na jaki okres można wynająć mieszkanie?`
  2. *(If bot clarifies — user replies:* `Chodzi o pierwszą / nową umowę najmu, nie przedłużenie.` *)*
- **Expected answer (acceptance criteria):**
  - **Turn 1:** MUST **clarify** pierwsza umowa vs przedłużenie OR ask minimum period intent — MUST NOT answer only **extension pricing / przedłużenie** tables.
  - **Turn 2 (or single-turn with „pierwsza” in question):**  
    `Na jaki okres można wynająć mieszkanie przy pierwszej / nowej umowie (minimum 12 miesięcy i ewentualne dopłaty)?`  
    MUST cover **minimum 12 miesięcy** for first lease and surcharges/dopłaty if in CONTEXT.
  - MUST NOT conflate **opcja przedłużenia** pricing with **nowy najem**.

### A10

- **Reporter / source:** Joanna Pertyk
- **Issue type:** DATA (Instrukcja vs practice)
- **Conversation:**  
  `Kiedy należy uiścić opłatę za wcześniejsze rozwiązanie umowy przy zamianie mieszkania — dzień przed rozwiązaniem czy przed podpisaniem nowej umowy / przekazaniem kluczy?`
- **Expected answer (acceptance criteria):**
  - MUST NOT state sole deadline **dzień przed planowanym rozwiązaniem** as the only correct rule (indexed Instrukcja error).
  - SHOULD prefer **przed podpisaniem nowej umowy** OR **przed przekazaniem kluczy do nowego lokalu** (tester practice).
  - MAY mention **1000 zł** fee only in **zamiana lokalu** context, not mixed with porozumienie kary.

### A11

- **Reporter / source:** Joanna Pertyk
- **Issue type:** DATA
- **Conversation:**  
  `Czy przy wcześniejszym rozwiązaniu wysyła się umowę rozwiązania razem z warunkami nowej umowy najmu?`
- **Expected answer (acceptance criteria):**
  - MUST NOT instruct as mandatory practice: **„wysyłamy porozumienie rozwiązujące razem z warunkami nowej umowy”** without noting this is outdated vs actual process.
  - SHOULD reflect tester rule: **porozumienie i warunki nowej umowy nie idą w jednym pakiecie** (or describe actual sequence).
  - If only stale Instrukcja in CONTEXT: MAY flag uncertainty — corpus fix tracked separately.

### A12

- **Reporter / source:** Joanna Pertyk
- **Issue type:** OUT_OF_SCOPE (acceptable)
- **Conversation:**  
  `Czy w ofercie jest ubezpieczenie od niepłacenia czynszu (poza ubezpieczeniem OC najemcy)?`
- **Expected answer (acceptance criteria):**
  - **PASS if:** honest **brak informacji w materiałach** / OUT_OF_SCOPE — no fabricated product.
  - MAY mention **OC najemcy (np. 50 tys.)** via the partner verification service only if in CONTEXT.
  - MUST NOT invent **ubezpieczenie od niepłacenia czynszu** details.
  - FAIL if: silent omission while pretending full coverage; or wrong insurance type conflated with OC.

### A13

- **Reporter / source:** Joanna Pertyk
- **Issue type:** GENERATION
- **Conversation:**  
  `Jakie są warunki podpisania umowy najmu dla osoby prywatnej, a jakie dla firmy (bez mieszania z warunkami technicznymi lokalu)?`
- **Expected answer (acceptance criteria):**
  - MUST **split** osoba prywatna vs firma (two clear sections or labeled lists).
  - MUST NOT dump mixed checklist with stray **„Inne”**, **OC firmy 200k**, **warunki techniczne lokalu** without labeling audience.
  - SHOULD trigger clarify on turn 1 if question is only „warunki podpisania” without osoba/firma (optional strict test).

### A14

- **Reporter / source:** Joanna Pertyk
- **Issue type:** GENERATION
- **Conversation:**  
  `Czym jest opcja wypowiedzenia przy przedłużeniu umowy i czy wiąże się z opłatą 1000 zł za wcześniejsze rozwiązanie?`
- **Expected answer (acceptance criteria):**
  - MUST distinguish **opcja wypowiedzenia przy przedłużeniu** from **1000 zł zamiana lokalu**.
  - MUST NOT equate opcja wypowiedzenia = opłata 1000 zł.
  - MAY cite **½ czynszu / max 3×** only for the correct instrument (porozumienie), not swap fee.
  - Context = **wypowiedzenie w trakcie przedłużenia**, not apartment swap only.

### A15

- **Reporter / source:** Joanna Pertyk; Klaudia Konicka
- **Issue type:** DATA
- **Conversation:**  
  `Czy bez numeru PESEL można korzystać z usługi weryfikacji partnera i jakie są progi kaucji (1,5 / 2 / 3 miesiące) oraz zasada czynszu powiększonego o 10% przy pozytywnej ścieżce?`
- **Expected answer (acceptance criteria):**
  - MUST include **kaucja = jeden miesiąc czynszu + 10%** on positive path (prominent, not buried).
  - MUST list tiers **1,5 / 2 / 3 miesiące** for negative paths when in CONTEXT.
  - SHOULD state **partner verification service** availability per tester policy (not „tylko manualnie” for all no-PESEL cases).
  - MUST NOT lead with stale **brak weryfikacji → 3 m-ce** as signing path.

### A16

- **Reporter / source:** Katarzyna Słowicka
- **Issue type:** DATA
- **Conversation:**  
  `Jaka kara za wcześniejsze rozwiązanie umowy 12-miesięcznej — połowa czynszu do końca okresu z maksimum trzech miesięcy czynszu?`
- **Expected answer (acceptance criteria):**
  - MUST state applicable cap for **12-month** context (tester expects **max 4 miesiące** / **min 1 miesiąc** where extension docs apply — not only Procesy ½/3×).
  - MUST NOT answer only **½ + max 3×** without contract-type qualification.
  - First sentence should contain **numbers** when composer active.

### A17

- **Reporter / source:** Katarzyna Słowicka
- **Issue type:** DATA / RETRIEVAL
- **Conversation:**  
  `Jaka opłata za wcześniejsze rozwiązanie umowy na okres 24 lub 36 miesięcy (zamiast połowy czynszu z limitem trzech miesięcy)?`
- **Expected answer (acceptance criteria):**
  - MUST prioritize **Przedłużenie** porozumienie: **max cztery miesiące czynszu**, **min jeden miesiąc**.
  - MUST NOT use only **Procesy** slide **½ / trzykrotność** for 24/36-month extension scenario.
  - MUST NOT produce vague RE analysis without numeric caps.

### A18

- **Reporter / source:** Klaudia Konicka
- **Issue type:** DATA
- **Conversation:**  
  `Jaka kaucja obowiązuje przy braku weryfikacji i czy umowa może być zawarta „do czterech miesięcy”?`
- **Expected answer (acceptance criteria):**
  - MUST NOT answer **brak weryfikacji → 3 miesiące kaucji** and **umowa do 4 miesięcy** as current combo.
  - SHOULD align with **brak podpisania** without verification.
  - MUST separate **okres umowy** from **wysokość kaucji** labels.

### A19

- **Reporter / source:** Joanna Pertyk (docx only)
- **Issue type:** OUT_OF_SCOPE (acceptable)
- **Conversation:**  
  `Czy firma dopłaca VAT do czynszu najmu?`
- **Expected answer (acceptance criteria):**
  - **PASS if:** **brak informacji w materiałach** / OUT_OF_SCOPE — no invented VAT subsidy policy.
  - MUST NOT fabricate „tak/nie” without corpus support.
  - FAIL if: confident wrong VAT answer or unrelated tax lecture without sources.

---

## B. UX, routing & answer quality

### B1

- **Reporter / source:** Joanna Pertyk (+ team)
- **Issue type:** UX / GENERATION
- **Conversation:**  
  `Jakie są zasady najmu krótkoterminowego?` *(or any deliberately broad topic in one sentence)*
- **Expected answer (acceptance criteria):**
  - MUST stay **on-topic** (rental domain) and address the asked subtopic first.
  - MUST NOT drift to unrelated procedures (e.g. only RE, only insurance) when question was narrow.
  - SHOULD be **concrete** in the requested area within first 2–3 sentences.

### B2 (multi-turn)

- **Reporter / source:** Klaudia Konicka — buried +10% kaucja
- **Issue type:** UX / GENERATION
- **Conversation:**
  1. `Jaka jest wysokość kaucji?`
  2. `A jeśli klient ma pozytywną weryfikację finansową?`
  3. `Jaka kaucja przy pozytywnej weryfikacji finansowej — czy to jeden czynsz plus 10%?`
- **Expected answer (acceptance criteria):**
  - **Turn 1:** MAY give overview but SHOULD NOT require 3 turns for basic policy; optional clarify (osoba/firma, pozytywna/negatywna) is OK.
  - **Turn 3:** MUST state clearly in **opening sentence**: **kaucja = jeden miesiąc czynszu + 10%** (pozytywna ścieżka).
  - MUST NOT hide +10% only in paragraph 4+ without numeric lead.
  - MUST NOT mix stale **4-miesięczna kaucja** or **brak weryfikacji → 3 m-ce** as headline for positive path.

### B3

- **Reporter / source:** Klaudia Konicka
- **Issue type:** UX
- **Conversation:**  
  Same as **B2 turn 2** — `A jeśli klient ma pozytywną weryfikację finansową?`
- **Expected answer (acceptance criteria):**
  - **+10% / jeden czynsz** rule MUST be **visible on first read** (heading, bold lead, or first sentence) — not only deep in bullet list.
  - PASS = skimmable structure; FAIL = „gdzieś w treści” bez wyróżnienia.

### B4 (multi-turn — clarify, do not guess)

- **Reporter / source:** Vlad (May 12 planned behavior); aligns with B4 issue
- **Issue type:** UX / clarify (code)
- **Conversation:**
  1. `Opisz cały proces najmu — od weryfikacji po podpisanie umowy.`
- **Expected answer (acceptance criteria):**
  - **Turn 1:** MUST return **1–2 clarifying questions** (e.g. osoba vs firma, pierwsza umowa vs przedłużenie, który etap procesu) — **no full procedural essay** from 200+ docs.
  - MUST NOT invoke long RAG answer guessing contract type.
  - After user clarifies in follow-up (not scripted here): then MAY retrieve and answer narrowly.
  - Related known limitation: broad queries stay **slow** (B5) — clarify path should still be fast (no Pinecone).

### B5

- **Reporter / source:** Vlad Nikoliuk (Apr 10)
- **Issue type:** RETRIEVAL / perf
- **Conversation:**  
  `Opisz cały proces najmu, weryfikacji, podpisania umowy i wydania lokalu krok po kroku.`
- **Expected answer (acceptance criteria):**
  - **Performance:** expect **longer latency** (many similar docs) — note time; not a functional fail alone.
  - SHOULD still be **coherent** and structured if answer completes.
  - If clarify gate enabled for extreme breadth: MAY ask to narrow scope instead of timeout-quality dump.
  - Document as known limitation until corpus optimization (see architecture doc).

---

## C. Positive control

### C4

- **Reporter / source:** Joanna Pertyk — [image7](assets/bot-feedback/joanna-docx/image7.png)
- **Issue type:** UX (positive)
- **Conversation:**  
  `Jak dodać kolejną osobę do umowy najmu w trakcie trwania umowy — czy potrzebny jest aneks i jakie dokumenty?`
- **Expected answer (acceptance criteria):**
  - MUST give **actionable procedural** answer (aneks / dokumenty / kroki) grounded in CONTEXT.
  - MUST NOT respond with clarify-only for this **specific** question.
  - PASS = correct, on-topic steps; use as regression that **specific questions still work** after clarify gate.

---

## Quick reference — issue type legend

| Label | Meaning |
|-------|---------|
| **DATA** | Wrong/missing facts — fix corpus or retrieval priority |
| **GENERATION** | Right docs retrieved but wrong synthesis |
| **RETRIEVAL** | Wrong doc family ranked first (e.g. Procesy vs Przedłużenie) |
| **UX** | Structure, burying numbers, off-topic |
| **clarify** | Should ask before RAG |
| **OUT_OF_SCOPE** | Honest „not in materials” is acceptable |

---

## Test case index

| ID | Multi-turn |
|----|------------|
| A1–A4, A6–A8, A10–A18 | No |
| A5, A9 | Yes |
| A12, A19 | OUT_OF_SCOPE OK |
| B1, B3, B5 | No |
| B2, B4 | Yes |
| C4 | No |

**Total test cases: 25** (A1–A19 = 19, B1–B5 = 5, C4 = 1).
