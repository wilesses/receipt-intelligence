# Receipt Intelligence OS DESIGN.md

Status: foundation design system, documentation only.
Scope: Flask/Jinja production UI, static CSS, and future UI work.
Source of truth: existing implementation in `app/web/static/style.css`, templates in `app/web/templates/`, and frozen product docs in `docs/architecture/freeze/`.

## Interface Philosophy

Receipt Intelligence OS is an evidence-led intelligence console for receipts. Receipts are source evidence; understanding is the product.

The interface starts with one time-bound conclusion, then reveals reason, evidence, and next decision. It should feel calm, precise, dark, premium, and operational only when the evidence requires action.

Default reading order:

1. Conclusion.
2. Reason.
3. Evidence.
4. Decision.

Briefing is finite. It is not a feed, chatbot, metric wall, or generic reporting dashboard. Quiet Mode is a valid result when evidence shows stability.

## Color Tokens

Use existing CSS custom properties from `app/web/static/style.css`.

```css
:root {
  color-scheme: dark;
  --bg: #090d12;
  --surface: #111820;
  --surface-raised: #17212b;
  --surface-soft: #17212b;
  --text: #f2f5f7;
  --text-secondary: #a6b1bd;
  --muted: #7f8b98;
  --line: #283541;
  --line-strong: #586b7c;
  --primary: #4da8e8;
  --primary-dark: #70baf0;
  --on-primary: #06131d;
  --teal: #35b987;
  --positive: #35b987;
  --warning: #e8b04c;
  --critical: #e6636b;
  --focus-ring: rgba(77, 168, 232, .42);
  --sidebar-width: 248px;
  --radius-sm: 6px;
  --radius: 8px;
  --motion-fast: 160ms;
  --motion-base: 200ms;
  --shadow: none;
  --shadow-overlay: 0 18px 44px rgba(0, 0, 0, .28);
}
```

Chart templates currently mirror these values:

- chart text: `#a6b1bd`
- chart grid: `rgba(166, 177, 189, .14)`
- chart primary: `#4da8e8`
- chart positive: `#35b987`
- chart warning: `#e8b04c`
- chart critical: `#e6636b`
- secondary chart accents: `#9b8afb`, `#55c2d8`, `#d78c5b`, `#78c2a4`, `#93a4b5`, `#cf7da3`

## Semantic Colors

- Primary / link / selected: `--primary`.
- Primary hover: `--primary-dark`.
- Success / stable / quiet / cheaper / clear evidence: `--positive`.
- Warning / suspicious / needs attention: `--warning`.
- Critical / spend up / expensive / error: `--critical`.
- Muted context / secondary metadata: `--muted`.
- Strong boundary / form boundary: `--line-strong`.
- Focus: `--focus-ring`, never color alone.

Semantic state must include text, label, icon, or structure. Color alone is not enough.

## Typography

Current implementation uses system fonts through Bootstrap and project CSS.

Recommended token roles:

- Display conclusion: 30-58px, weight 750-760, line-height 1.08-1.12.
- Page title: 26-34px, weight 700+, line-height 1.12-1.15.
- Section title: 18-24px, weight 700+, line-height 1.2-1.25.
- Body: 15-17px, line-height 1.5-1.65.
- Metadata: 10-13px, weight 700-850, uppercase only for compact system labels.
- Numeric evidence: tabular figures via `font-variant-numeric: tabular-nums`.

Typography must serve reading order. Do not use marketing hero type. Do not scale font size directly with viewport width except already bounded `clamp()` usage for the briefing conclusion.

## Spacing

Use existing spacing rhythm:

- Compact gaps: 4px, 6px, 8px, 10px, 12px.
- Component gaps: 14px, 16px, 18px, 20px, 24px.
- Panel padding: 14px mobile, 20px default.
- Briefing/detail padding: 24px, 32px, 44px, 56px, 64px, 72px by available width.
- Dashboard grid gap: 16px.
- Charts/content grid gap: 18px.
- App container max width: existing `app-container` rules.

Keep information dense but readable. Prefer row structure and evidence bands over stacks of floating cards.

## Radius

Use existing radius scale:

- `--radius-sm: 6px` for compact controls, marks, and small affordances.
- `--radius: 8px` for buttons, inputs, panels, table links, and cards.
- `999px` only for true pills/badges such as category or price status.
- Circular only for counts or icon-only controls with equal width/height.

Avoid large rounded marketing cards.

## Surface Hierarchy

The interface is dark-first and border-led.

1. Page canvas: `--bg`.
2. Primary surface: `--surface`.
3. Raised / nested surface: `--surface-raised`.
4. Soft grouped surface: `--surface-soft`.
5. Dividers and table rows: `--line`.
6. Strong section boundaries: `--line-strong`.
7. Overlay depth: `--shadow-overlay`.

Default shadow is `none`. Depth comes from surface contrast, hairline borders, grids, and evidence structure. Use overlay shadow only for floating UI that truly overlays content.

## Component List

Existing foundation:

- App shell: `.app-shell`, `.app-nav-frame`, `.nav-group`, `.nav-link`, `.brand-mark`.
- Page frame: `.page-content`, `.app-container`, `.page-header`, `.command-header`, `.command-controls`.
- Shared surfaces: `.surface`, `.command-panel`, `.metric-card`.
- Forms: `.form-control`, `.form-select`, `.filters-grid`, `.search-control`, `.period-control`.
- Buttons and links: `.btn-primary`, `.btn-outline-primary`, `.btn-outline-secondary`, `.text-link`, `.icon-link`.
- Tables: `.table-responsive`, `.app-table`, `.sort-button`, `.amount-cell`, `.file-cell`.
- State messaging: `.inline-status`, `.state-message`, `.state-neutral`, `.state-success`, `.state-warning`, `.state-error`.
- Upload: `.upload-layout`, `.dropzone`, `.file-list`, `.file-pill`, `.progress`, `.status-line`.
- Dashboard command center: `.command-layout`, `.pulse-panel`, `.action-panel`, `.trend-panel`, `.movement-panel`, `.recent-panel`, `.health-panel`.
- Action queue: `.action-queue`, `.action-row`, `.severity-mark`, `.severity-critical`, `.severity-high`, `.severity-medium`, `.severity-low`.
- Intelligence Briefing: `.dispatch`, `.dispatch-masthead`, `.dispatch-stamp`, `.dispatch-verdict`, `.dispatch-band`, `.dispatch-dossiers`, `.dispatch-register`.
- Evidence trace: `.claim-trace`, `.trace-toggle`, `.trace-body`, `.dossier`, `.dossier-proof`, `.dossier-action`.
- Receipt archive: `.receipt-archive`, `.register-list`, `.register-row`, receipt table rows.
- Analytics: `.analytics-metrics`, `.total-chip`, `.charts-grid`, `.chart-card`, `.chart-frame`, `.link-strip`, `.trend-toolbar`.
- Review operations: `.review-list`, `.review-card`, `.review-card-main`, `.review-category-form`, `.review-meta`, `.technical-details`.
- Data health / price quality: `.health-list`, `.health-row`, `.health-track`, `.price-status`, `.price-evaluation`, price quality tables.
- Product operations: `.suggestions-list`, `.suggestion-card`, `.suggestion-reasons`, `.confidence-badge`, `.alias-list`, `.category-badge`.

## Screen Roles

Dashboard / Briefing:
Lead with the dominant conclusion. Show period, comparison, spend, shift, source count, and forecast as supporting context. Findings unfold through Change, Reason, Significance, Evidence, Action.

Action Queue:
List-like, ranked, capped, severity-marked. It exists to route cleanup work that improves evidence quality. It must not become a notification feed.

Archive:
Receipt source evidence. Search, sort, and open records. Archive is subordinate to intelligence, but must remain fast and trustworthy.

Analytics:
Question-answering surface with filters and charts. Charts support investigation; they are not the opening identity of the product.

Review:
Operational correction surfaces for categories, product suggestions, merges, and price quality. They must preserve evidence and manual authority.

Data Health:
Shows coverage, unresolved records, confidence, suspicious prices, stale or incomplete evidence. It should explain what intelligence is safe to trust.

## Responsive Behavior

Desktop:
Persistent left navigation at `--sidebar-width`. Dense content grid. Evidence and briefing sections can use multi-column layouts.

Tablet:
Collapse complex grids to fewer columns. Preserve conclusion-first order and evidence continuity.

Mobile:
Single reading column. Keep controls full width. Do not hide evidence behind unrelated navigation. At 320 CSS pixels and 200% text scaling, content remains usable without horizontal page scrolling.

Reduced motion:
Keep `@media (prefers-reduced-motion: reduce)`. Motion cannot be required to understand state.

## Prohibited Patterns

Never introduce:

- Newsfeed / infinite feed.
- Glow, neon aura, bokeh, decorative gradient orb, or atmospheric AI effect.
- Marketing hero section.
- Generic KPI grid as the first screen.
- Equal-weight dashboard card wall.
- Decorative AI avatar, chatbot chrome, magic sparkle, or "AI-powered" ornament.
- Chart wall without a written claim and evidence context.
- Floating cards inside cards.
- Page sections styled as decorative cards.
- Color-only status.
- Moralizing spend, urgency without evidence, or fear-based copy.
- New top-level navigation for every intelligence domain.
- AI-generated prose as evidence.

## Future Work Rule

Before adding or changing UI, name the Claim or user question it serves, the evidence behind it, the decision it enables, and how the user can trace or correct it. If that answer is weak, do not build the UI.
