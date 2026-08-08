# Parser Hardening v2: Price Semantics + Measurement Parsing

Date: 2026-08-08
Status: implemented 2026-08-08; no schema migration or historical database write

## 1. Decision

Parser Hardening v2 strengthens the existing Rimi and Maxima pipeline in place. It does not replace the parser, introduce a second price model, or expand the category subsystem.

The selected approach is corpus-driven hardening: preserve `parse_receipt()` and `derive_price_data()` as the shared boundaries, add narrow semantic rules backed by real receipt fixtures, normalize paid-price semantics for new imports, and leave ambiguous cases reviewable. Receipt #374 is the primary end-to-end golden fixture.

No schema migration or historical write-backfill belongs to this release. Existing rows remain readable through compatibility fallbacks.

## 2. Goals and scope

### In scope

- Rimi and Maxima parsing in `app/receipt_parser.py`.
- Price derivation and validation in `app/price_model.py`.
- Import/persistence handoff in `app/importer.py` and `app/db.py` only as needed to enforce the target contract for new rows.
- Receipt Detail, Product Dossier, and Price Quality labels and review signals.
- Deterministic interpretation of age/package forms (`6+110g`, `6+ 110g`, `4+90g`), true multipacks (`6x110g` and script/spacing variants), and weighted products (`Sīpoli 45+ kg`, including `2. šķ.` suffixes).
- Arithmetic validation, warning taxonomy, confidence effects, and read-time mismatch detection.
- Unit, parser, integration, UI, regression-corpus, and read-only audit tests.
- A sanitized text fixture derived from the source PDF for receipt #374.

### Non-goals

- Category engine, category correction, classification, category UI, or category backfill.
- Lidl/other merchants, universal parsing, OCR work, Gmail behavior, or upload redesign.
- Wholesale parser rewrite, product-identity/name-layer redesign, or ML/LLM parsing.
- New fields for listed prices, discounts, age, multipack components, or persisted warnings.
- Historical data rewrite during deployment.
- Forced reconciliation of every receipt header total with product rows; service lines may be intentionally excluded.

## 3. Existing project inventory

- `app/receipt_parser.py`: `parse_receipt()` selects Rimi/Maxima. Rimi extracts quantity/unit and a receipt-listed `unit_price`, then may replace `price` with discounted `Gala cena`. Maxima extracts quantity and paid `price`, but emits `quantity_unit="unknown"` and no structured listed unit price.
- `app/importer.py`: extracts PDF text, calls the parser and `derive_price_data()`, then copies dataclass fields into each item. Returned `warnings` are not persisted by the database layer.
- `app/db.py`: writes both `items.price` and `items.line_total` from `price_data.line_total`; Price Model columns are additive and nullable for legacy rows.
- `app/price_model.py`: recognizes one package measurement, rejects unresolved multipacks/ambiguity, computes paid normalized prices from `line_total`, and emits transient validation warnings. Its current arithmetic tolerance is `max(€0.02, 2% of line_total)`.
- `app/web/templates/receipt.html`: labels paid row total as `Цена`.
- `app/web/templates/_product_dossier_components.html`: labels `line_total` as `Цена упаковки` and `unit_price` as `Цена за строку`, reversing their intended meanings.
- `app/web/routes.py`: review status is based mainly on confidence and normalized-price bounds; Price Quality does not independently catch every arithmetic mismatch.
- `tests/test_receipt_parser.py`, `tests/test_price_model.py`, `tests/test_ui_shell.py`, `tests/test_item_profile_ui.py`, and `tests/test_price_quality_ui.py` cover the affected layers, but no existing golden test runs receipt #374 end to end.

## 4. Approaches considered

1. **Package-regex patch only — rejected.** It would repair two RŪDOLFS names but leave Maxima units, mixed `unit_price` semantics, weighted suffixes, diagnostics, and UI inconsistent.
2. **Full item-block parser rewrite — rejected for v2.** It could model listed prices and multipacks cleanly, but creates unnecessary regression risk across the existing Rimi/Maxima corpus.
3. **Semantic hardening at existing boundaries — selected.** Keep merchant extraction and Price Model boundaries, separate token recognition from interpretation for the ambiguous forms in scope, normalize paid-price semantics, and protect behavior with real fixtures.

## 5. Current field contract

| Field | Current meaning | Current problem |
|---|---|---|
| `price` | Legacy paid total for the complete item row after discounts. | Name/UI can imply a unit price. |
| `line_total` | Additive copy of paid item-row total when populated. | Nullable on legacy rows; duplicates `price`. |
| `quantity` | Purchased piece count or physical amount. | Ambiguous without `quantity_unit`. |
| `quantity_unit` | `piece`, `kg`, `g`, `l`, `ml`, or `unknown`. | Maxima commonly remains `unknown`; many fractional legacy rows lack units. |
| `unit_price` | Mixed: effective paid amount per purchased unit for Maxima/backfill, often receipt-listed pre-discount price for Rimi. | `quantity × unit_price` can conflict with paid total. |
| `package_size` | Size of one purchased package in base grams, millilitres, or contained pieces. | `6+110g` is rejected; old logic can misread `45+ kg`; multipacks lack representation. |
| `package_unit` | `g`, `ml`, `piece`, or `unknown`. | Depends on extraction quality. |
| `normalized_unit_price` | Paid EUR/kg, EUR/L, or EUR/piece calculated from `line_total`. | Can be correct while `unit_price` conflicts. |
| `normalized_price_unit` | Exact normalization denominator or `unknown`. | UI sometimes hides the basis. |
| `price_parse_source` | Source of measurement/normalization interpretation. | Can be mistaken for source of the receipt price. |
| `price_parse_confidence` | Confidence in normalization. | Can be mistaken for OCR/whole-row confidence; high value may coexist with conflict. |

Audited compatibility fact: whenever `line_total` is populated, it equals `price`. Spending analytics based on `SUM(price)` remain valid.

## 6. Target field contract

The target applies to every newly imported item after v2.

| Field | Target meaning/invariant |
|---|---|
| `price` | Legacy alias of paid item-row total; equals `line_total`. |
| `line_total` | Canonical amount actually paid for the full item row after row-level discounts. |
| `quantity` | Purchased amount expressed in `quantity_unit`: package/item count for `piece`, physical amount otherwise. |
| `quantity_unit` | Deterministically supported normalized unit; otherwise `unknown`. |
| `unit_price` | Effective paid price per unit of `quantity`: `line_total / quantity`; never the listed pre-discount price. |
| `package_size` | Net size of one purchased `piece` in base `g`, `ml`, or contained `piece`; null for weighted goods and unresolved multipacks. |
| `package_unit` | Base unit for `package_size`; `unknown` when absent. |
| `normalized_unit_price` | Paid price derived from `line_total` in EUR/kg, EUR/L, or EUR/piece. |
| `normalized_price_unit` | Exact denominator; `unknown` when evidence is insufficient. |
| `price_parse_source` | Provenance of measurement/normalization interpretation, retained under its existing schema name. |
| `price_parse_confidence` | Confidence in measurement/normalization after validation caps, never OCR/whole-item confidence. |

Required invariants for new rows:

1. `price == line_total` at stored currency precision.
2. For `quantity > 0`, `unit_price == round(line_total / quantity, 4)`.
3. `abs(quantity × unit_price − line_total) <= €0.02`; larger difference is a mismatch.
4. Normalized price is always calculated from paid `line_total`.
5. `package_size` describes one purchased piece; it never consumes purchased quantity, age, or caliber.
6. Ambiguous measurement produces null/unknown derived fields plus a warning, not a guess.
7. Invalid quantity/total/package/unit evidence cannot produce a trusted normalized price.

### Listed prices and discounts

The current schema has no unambiguous destination for printed pre-discount values. In v2, the source PDF/text remains provenance, `unit_price` becomes the effective paid value, and structured `listed_unit_price`, `listed_line_total`, and `discount_total` are deferred to a separate additive migration. This deliberately removes mixed meaning from `unit_price` without smuggling a schema migration into hardening.

## 7. Parsing and semantic precedence

Interpret measurement tokens only after the merchant parser identifies the complete name block and price/quantity line. Apply this precedence:

### 7.1 Explicit merchant evidence

- Rimi `N gab X P EUR [T]` → `quantity=N`, `quantity_unit=piece`.
- Rimi `N kg X P EUR/kg [T]` → `quantity=N`, `quantity_unit=kg`.
- Maxima `P X N gab. T` → `quantity=N`, `quantity_unit=piece`.
- Maxima fractional `P X N T` plus a supported weighted name marker → physical quantity/unit.
- Paid `line_total` comes from the final-discount line when present, otherwise printed row total; stored `unit_price` is then derived from paid total.

Explicit merchant evidence outranks name inference, while arithmetic validation still applies.

### 7.2 Age marker plus package

Recognize an age marker only when a one/two-digit value in the supported 1–36 month range plus `+` is immediately followed (optional whitespace) by a second numeric token in `g` or `ml`, the second token is a plausible single-package size, and no multiplication sign is present.

| Token | Interpretation |
|---|---|
| `6+110g` | age `6+`; package 110 g |
| `6+ 110g` | age `6+`; package 110 g |
| `4+90g` | age `4+`; package 90 g |
| `12+ 200ml` | age `12+`; package 200 ml |

The age token remains in the stored/display name. No age field is added. It contributes neither to quantity nor package size. Unsupported/conflicting forms remain ambiguous.

### 7.3 True multipack

`count x size unit` with `x`, Cyrillic `х`, or `×` (optional whitespace) is a multipack candidate: `6x110g`, `6 x 110 g`, `6х110g`, `6×110g`.

The current schema cannot preserve count and component size. Therefore v2 keeps it unresolved: null package/normalized values, `multipack_unresolved`, and absent/below-threshold confidence. The original name is preserved; it is never reinterpreted as `6+110g`, one 110 g package, or one 660 g package.

### 7.4 Weighted items and caliber

For `Sīpoli 45+ kg` and `Sīpoli 45+ kg 2. šķ.`:

- `45+` is caliber/grade, not package mass or age;
- with fractional merchant quantity and consistent price-line evidence, `kg` is the sales unit;
- `quantity_unit=kg`, package fields stay empty;
- `unit_price=line_total/quantity`;
- normalized price is the same effective EUR/kg value.

The recognizer accepts an explicit terminal physical unit or that unit followed by a narrow allowlist of merchant qualifiers such as `2. šķ.`. It does not search arbitrary interior text.

Negative cases:

- `Miltu maiss 45kg` bought as one piece remains an ambiguous large package.
- `Produkts 45+ kg` with integer quantity and no weighted evidence remains unresolved.
- `6+110g` is package/age, not weighted.
- `6x110g` is multipack, not weighted.

When two interpretations remain plausible, preserve name and paid total but leave measurement-derived fields unresolved.

## 8. Validation and warnings

Retain existing warnings and add only `age_package_ambiguous` and `weighted_measurement_ambiguous` where the narrow new grammars fail. Existing relevant warnings include `line_total_unit_price_mismatch`, unit/quantity/price errors, package ambiguity, `multipack_unresolved`, normalized-price bounds, `service_line`, and `parser_contamination`.

Rules:

- Currency consistency uses absolute €0.02 tolerance.
- Printed unit price may validate merchant extraction, but stored `unit_price` uses paid total.
- Weighted printed evidence is consistent when printed quantity × printed physical-unit price reproduces printed row total within €0.02.
- Tests compare four-decimal normalized results with four-decimal tolerance.
- Fatal evidence warnings prevent trusted normalization.
- Arithmetic mismatch preserves paid totals but caps confidence below `0.75`.
- Explicit physical-unit evidence may survive unrelated package-name ambiguity; unused package fields remain empty.
- Confidence cannot remain `0.95` when validation finds a mismatch.

No warning column is added. Runtime/audit results retain explicit identifiers; persisted confidence/source reflect safety; Price Quality independently calculates mismatch from stored columns. This removes the contradiction where transient warnings vanish while UI appears verified.

## 9. UI semantics

All displayed paid totals use `COALESCE(line_total, price)` so legacy rows remain readable.

### Receipt Detail

- Rename heading/mobile label `Цена` to `Итого за позицию`.
- Piece quantity over one: `2 шт. · 1,55 €/шт. · итого 3,10 €`.
- Weighted item: `0,580 кг · 0,91 €/кг · итого 0,53 €`.
- Single packaged item may show normalized price as secondary context.
- Omit unresolved fragments rather than inventing a denominator.
- Label the row sum as stored product-row sum; do not call a header difference a missing item because excluded service lines may explain it.

### Product Dossier

- `line_total`/fallback `price` → `Итого за позицию`.
- `unit_price` → `Оплачено за единицу` with denominator.
- package fields → `Размер упаковки`.
- normalized value → `Сопоставимая цена` with explicit unit.
- provenance/confidence → `Источник нормализации` / `Уверенность нормализации`.
- Purchase register `Цена` becomes `Итого за позицию`.
- Existing legacy monthly charts remain explicitly labeled as not package-normalized.

### Price Quality

- Add deterministic mismatch condition for positive quantity and non-null total/unit price with absolute difference over €0.02.
- Include it in all-problems even if stored confidence is high; a dedicated filter may be added without breaking existing URLs.
- Explain the conflicting arithmetic without asserting which source value is correct.
- Confidence wording always refers to normalization.

## 10. Golden fixture: receipt #374

Source: current receipt `374`, PDF/receipt number `2870-0120-7780-1593`, MAXIMA, 2026-08-07, header total €31.00. Check in a stable UTF-8 excerpt with product blocks, price/quantity lines, discounts, total, and service line; exclude personal/payment footer data. Tests must not depend on production DB or absolute PDF paths.

| Product | Qty/unit | Total | Effective unit | Package | Normalized |
|---|---:|---:|---:|---:|---:|
| Dzeramais ūdens AQUA negāzēts 5L | 1 piece | €0.97 | €0.9700 | 5000 ml | 0.1940 €/L |
| BIO biez. RŪDOLFS dārz. rīsi vista 6+ 110g | 1 piece | €1.74 | €1.7400 | 110 g | 15.8182 €/kg |
| BIO biez. RŪDOLFS sald. kartup. burk. 6+110g | 1 piece | €1.48 | €1.4800 | 110 g | 13.4545 €/kg |
| BIO biez. RŪDOLFS aprik. ban. ķirbju 6+110g | 1 piece | €1.48 | €1.4800 | 110 g | 13.4545 €/kg |
| Saldēti frī kartupeļi AVIKO Steak 750g | 1 piece | €2.62 | €2.6200 | 750 g | 3.4933 €/kg |
| Cāļa filejas šašliks Cēzara mar. RM 700g | 1 piece | €6.83 | €6.8300 | 700 g | 9.7571 €/kg |
| Liell. g. uzkoda Beef Jerky Classic WD 40g | 1 piece | €2.23 | €2.2300 | 40 g | 55.7500 €/kg |
| Vār. Doktordesa MELNAIS BARONS 400g | 1 piece | €2.33 | €2.3300 | 400 g | 5.8250 €/kg |
| Nūd. zupa NONGSHIM KIMCHI RAMYUN 120g | 2 piece | €3.10 | €1.5500 | 120 g | 12.9167 €/kg |
| Vīns ZIBOMARE Zibibbo 12% 0,75L | 1 piece | €6.99 | €6.9900 | 750 ml | 9.3200 €/L |
| Proteīna dzēr. PIENA SPĒKS šokolādes 460g | 1 piece | €1.04 | €1.0400 | 460 g | 2.2609 €/kg |

Additional assertions:

- exactly 11 product rows in source order;
- paper shopping bag at €0.19 is recognized as a service line and excluded;
- product rows sum to €30.81; plus excluded €0.19 reconciles to €31.00;
- all three RŪDOLFS rows produce 110 g, never package count 6;
- NONGSHIM renders `2 шт. · 1,55 €/шт. · итого 3,10 €`;
- no category assertion exists.

## 11. Test strategy

### Price Model unit tests

- Positive age/package forms and negative malformed/conflicting/implausible forms.
- Multipack variants across `x`, `х`, and `×` stay unresolved.
- `45+ kg` never becomes `45000 g`.
- Weighted inference accepts fractional consistent evidence and rejects integer/inconsistent cases.
- Paid effective unit price, `price == line_total`, normalized values, and the €0.02 boundary.
- Confidence caps and fatal-warning behavior independently of rendering.

### Parser tests

- Rimi discounted piece/weighted rows produce paid effective unit price.
- Maxima `gab.` normalizes to `piece` and weighted blocks capture physical unit from narrow product context.
- Multiline name assembly preserves `6+110g`/`40g` without metadata contamination.
- Existing service, decimal, malformed-token, discount, and merchant cases remain green.

### End-to-end golden test

Run sanitized #374 text through the production pre-persistence path: parser, product-name normalization, and Price Model. Assert metadata, order, every table field, service behavior, and reconciliation. Any persistence test uses temporary SQLite only.

### UI and audit

- Assert corrected labels, NONGSHIM display, weighted/unresolved behavior, and legacy fallback.
- Assert Price Quality catches high-confidence arithmetic conflicts and uses normalization-confidence wording.
- Run the full suite and a read-only current-corpus projection.
- Require zero new false-positive package extraction; manually review every newly resolved plus/weighted audit case. Audit never authorizes a write.

## 12. Acceptance criteria

- Every newly persisted item has `price == line_total` and effective `unit_price` to four decimals.
- No mismatch over €0.02 appears fully verified; normalized price uses paid total only.
- Legacy null-`line_total` rows render/aggregate through `price`.
- Age/package cases extract only the second number; true multipacks remain distinct and unresolved.
- Supported `45+ kg` weighted cases resolve only with fractional merchant evidence; caliber never becomes package mass.
- Ambiguity stays unresolved/reviewable.
- Receipt Detail/Product Dossier never call row total a unit/package price.
- Price Quality includes arithmetic conflicts regardless of stored confidence.
- Receipt #374 passes all exact expectations above.
- Existing tests pass after intentional assertions; no category logic/data/test enters scope.
- Production DB checksum is unchanged by implementation verification absent separately approved write work.

## 13. Migration and backfill boundaries

Deployment performs no schema/data migration. New semantics apply to new imports; existing Price Model values are untouched and analytics keep `price` for spend.

After implementation, a separate read-only projection may cover the 1,341 audited legacy rows with null Price Model fields, 315 fractional rows without physical units, arithmetic conflicts, and plus/caliber/multipack candidates. It must report row-level before/after fields, warnings, source/confidence distributions, resolution counts, and high-confidence conflicts.

Any later write-backfill requires a separate design/plan and explicit approval, with immutable dry-run, reviewed diff, pre-run SHA-256, verified SQLite Backup API backup, allowlisted sources, downgrade protection, preservation of manual-review/high-confidence conflicts, one transaction, post-write integrity/count/checksum checks, and a restore procedure. Listed-price, discount, warning, age, and multipack fields likewise require separate additive schema approval.

## 14. Rollback and failure risks

- **Age/caliber confusion:** require a second numeric `g`/`ml` token; `45+ kg` never matches age/package.
- **Multipack regression:** give `x`/`х`/`×` recognition higher precedence.
- **Discount evidence:** effective unit price no longer holds listed price; source PDF remains authoritative pending additive fields.
- **Weighted false positives:** require fractional quantity, narrow suffix grammar, and printed-price arithmetic evidence.
- **Transient warnings:** cap confidence before persistence and compute mismatch independently in Price Quality.
- **Legacy mixed semantics:** use compatibility fallback and read-only audit; never silently rewrite.
- **Rounding drift:** implementation should use decimal receipt amounts and fixed €0.02 tolerance.
- **Receipt-total confusion:** label product-row sum honestly; #374 proves the €0.19 service-line case.
- **Dirty worktree:** stage only explicit task paths; never reset, clean, restore, or overwrite unrelated work.

Code/UI rollback is a normal revert. Because deployment has no backfill, existing DB restore is unnecessary. Receipts imported after deployment are user data and must not be deleted; corrections require a separately approved repair. A future failed backfill restores only from its verified backup after explicit confirmation.

## 15. Planned implementation surface

The later implementation plan should use the smallest necessary subset of:

- `app/receipt_parser.py`
- `app/price_model.py`
- `app/importer.py`
- `app/db.py`
- `app/web/routes.py`
- `app/web/templates/receipt.html`
- `app/web/templates/_product_dossier_components.html`
- `app/web/templates/_diagnostic_components.html`
- affected parser/price/UI tests
- one sanitized text fixture under `tests/fixtures/`

Category files/tests, production DB, source PDFs, and Obsidian Vault are excluded. Implementation documentation updates are deferred until behavior exists.

## 16. Implementation-phase definition of done

1. Target contracts and acceptance criteria are implemented.
2. Receipt #374 passes from sanitized text through derived fields and UI semantics.
3. Focused/full tests pass apart from explicitly documented unrelated pre-existing failures.
4. Read-only corpus audit reports no new false-positive package/weighted interpretations.
5. Production SQLite integrity/checksum remain unchanged by verification.
6. Documentation matches implemented behavior.
7. No category, schema migration, or historical write-backfill change is included.
