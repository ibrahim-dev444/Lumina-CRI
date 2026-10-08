---
name: Lumina System
colors:
  surface: '#f9f9ff'
  surface-dim: '#d2daf0'
  surface-bright: '#f9f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f1f3ff'
  surface-container: '#e9edff'
  surface-container-high: '#e0e8ff'
  surface-container-highest: '#dbe2f9'
  on-surface: '#141b2c'
  on-surface-variant: '#3e4947'
  inverse-surface: '#293041'
  inverse-on-surface: '#edf0ff'
  outline: '#6e7977'
  outline-variant: '#bec9c6'
  surface-tint: '#016a62'
  primary: '#00544d'
  on-primary: '#ffffff'
  primary-container: '#0b6e66'
  on-primary-container: '#9bede3'
  inverse-primary: '#84d5cb'
  secondary: '#525f73'
  on-secondary: '#ffffff'
  secondary-container: '#d6e3fb'
  on-secondary-container: '#586579'
  tertiary: '#753a21'
  on-tertiary: '#ffffff'
  tertiary-container: '#925136'
  on-tertiary-container: '#ffd6c7'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#a0f1e7'
  primary-fixed-dim: '#84d5cb'
  on-primary-fixed: '#00201d'
  on-primary-fixed-variant: '#00504a'
  secondary-fixed: '#d6e3fb'
  secondary-fixed-dim: '#bac7de'
  on-secondary-fixed: '#0f1c2d'
  on-secondary-fixed-variant: '#3b485a'
  tertiary-fixed: '#ffdbce'
  tertiary-fixed-dim: '#ffb598'
  on-tertiary-fixed: '#370e00'
  on-tertiary-fixed-variant: '#70361e'
  background: '#f9f9ff'
  on-background: '#141b2c'
  surface-variant: '#dbe2f9'
typography:
  headline-lg:
    fontFamily: IBM Plex Sans
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: IBM Plex Sans
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.005em
  headline-sm:
    fontFamily: IBM Plex Sans
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
  body-lg:
    fontFamily: IBM Plex Sans
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-md:
    fontFamily: IBM Plex Sans
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: IBM Plex Sans
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  label-lg:
    fontFamily: IBM Plex Sans
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 16px
  label-md:
    fontFamily: IBM Plex Sans
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
  label-sm:
    fontFamily: IBM Plex Sans
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.04em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1rem
  margin: 2rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1rem
  space-xl: 1.5rem
---

## Brand & Style

This design system is engineered for enterprise banking data stewardship and golden customer record reconciliation. Its character is utilitarian, hyper-structured, dense, and calm. Visual noise is strictly eliminated to minimize cognitive fatigue during prolonged analysis of mission-critical institutional data.

The system takes structural inspiration from modern technical control planes (such as the Stripe Dashboard and Linear), balancing information density with instant scannability. Precision, trust, and predictability define the visual standard. Every element serves an operational purpose: no decorative illustrations, no gradients, no glassmorphic blurs, and no expressive iconography. Contrast is deliberate and crisp, allowing data stewards to verify, reconcile, and merge entity graphs with complete confidence.

## Colors

The palette establishes a restrained, low-glare working canvas that preserves visual endurance across complex workflows.

- **Canvas & Surfaces**: The default application canvas uses `#F6F7F9`, a pale cool-grey that provides structural contrast against pure white (`#FFFFFF`) cards, tables, and inspection panels without relying on shadows.
- **Primary Accent (`#0B6E66`)**: Deep Teal is reserved strictly for high-intent operational triggers: primary actions, the active navigation indicator, entity commit flows, and golden-record quality/confidence score meters. It is never used decoratively or for generic links.
- **Neutrals**:
  - Primary text: `#101828` on headers, critical metrics, and canonical record values.
  - Secondary text: `#475467` for form labels, descriptions, and active filters.
  - Tertiary / Muted text: `#667085` for table column headers, helper text, and timestamps.
  - Borders: `#E4E7EC` for outer containers, inputs, and card bounds.
  - Dividers: `#F2F4F7` for tabular row separators and internal component sectioning.
- **Status Semantic Palette**:
  - Positive / High Trust: Text `#027A48`, dot `#12B76A`, background tint `#ECFDF3`.
  - Warning / Medium Trust: Text `#B54708`, dot `#F79009`, background tint `#FEF0C7`.
  - Critical / Low Trust / Discrepancy: Text `#B42318`, dot `#F04438`, background tint `#FEF3F2`.
  Status presentations require both a 6px solid dot and explicit text labels to ensure accessibility and rapid pattern recognition.

## Typography

Typography prioritizes legibility, systematic vertical rhythm, and numeric consistency across dense data grids.

- **Primary Typeface**: `IBM Plex Sans` anchors all titles, body copy, and UI controls. Its distinct geometric forms and neutral terminals preserve clarity at 12px and 13px table sizes.
- **Monospaced Data**: Customer IDs (e.g., `CUST-88392-X`), upstream source keys (`SWIFT-BIC`, `CORE-ACNT`), transaction hashes, and match scores (`0.00` to `1.00`) must be rendered using `IBM Plex Mono` with `font-variant-numeric: tabular-nums`. This guarantees strict vertical alignment across comparative reconciliation views.
- **Hierarchy & Case**:
  - Page Titles: 22px, Semi-Bold (`weight: 600`), 28px line-height.
  - Section Headers: 16px, Semi-Bold (`weight: 600`), 24px line-height.
  - Table Headers & Micro Meta: 11px/12px, Medium (`weight: 500`/`600`), uppercase tracking applied to technical labels to differentiate structural field headers from field values.
  - Body Text: 14px default, 20px line-height, regular (`weight: 400`).

## Layout & Spacing

The structural layout uses an explicit desktop-first shell optimized for wide financial data workspaces:

- **Sidebar Navigation**: Fixed 248px width dock running the full height of the viewport, containing identity contexts, workspace switchers, and stewardship queues.
- **Main Content Shell**: Fluid up to a maximum constrained width of `1280px` (`max-width: 1280px`) with an outer padding margin rhythm of `32px` (`2rem`) on desktop.
- **Interior Grid**: A fluid 12-column layout utilizing `16px` gutters (`gutter: 1rem`) for data comparisons, entity merge panels, and audit cards.
- **Density Control**:
  - Primary tables use compact padding: `8px` vertical cell padding and `12px` horizontal padding to maximize visible records above the fold.
  - Form groups and metadata sidebars use `12px` (`space-md`) vertical gaps between attributes.
  - Cards and structural panels maintain an internal padding of `20px` to `24px`.

## Elevation & Depth

This design system is strictly non-skeuomorphic and flat. Drop shadows (`box-shadow`) are prohibited on cards, data rows, inline panels, and navigation items (`box-shadow: 0 0 0 0 transparent`).

- **Surface Separation**: Depth is achieved entirely via high-contrast boundaries: `1px solid #E4E7EC` outlines set against the `#F6F7F9` background.
- **Interactive Layers**: Modals, filter dropdowns, and context tooltips employ a sharp border `1px solid #D0D5DD` paired with a minimal system utility border rather than heavy ambient blurs. Overlays use a solid neutral wash (`rgba(16, 24, 40, 0.4)`), avoiding blur effects.
- **State Highlighting**: Active selections, hovering table rows, and targeted record merges are highlighted through subtle surface fills (`#F9FAFB` on row hover) rather than directional lift or elevation shifts.

## Shapes

The geometric framework balances structural authority with modern fintech software convention:

- **Cards & Primary Panels**: Set to a standardized radius of `12px` (`border-radius: 12px; border: 1px solid #E4E7EC`).
- **Interactive Controls (Inputs, Buttons, Dropdowns)**: Set to `6px` radius to maintain a compact, tool-like precision.
- **Status Tags & Badges**: Set to `4px` or `6px` radius (avoid full pill radiuses) to preserve the tabular, block-like technical presentation.
- **Data Score Bars**: Outer track and fill indicators use a sharp `4px` corner to integrate cleanly with numerical readouts.

## Components

### Buttons
- **Primary**: Background `#0B6E66`, text `#FFFFFF`, border `1px solid #085D56`, radius `6px`. Hover: `#085D56`. Focused: 2px ring offset `#0B6E66`. Used only for definitive stewardship resolutions (e.g., "Confirm Match", "Merge Customer Record", "Export Canonical Set").
- **Secondary**: Background `#FFFFFF`, text `#344054`, border `1px solid #D0D5DD`, radius `6px`. Hover: `#F9FAFB`.
- **Destructive**: Background `#FFFFFF`, text `#B42318`, border `1px solid #FDA29B`. Hover: `#FEF3F2`.

### Status Indicators & Badges
- Strict composition: Always a centered `6px` circular dot positioned 6px to the left of label text.
- **High Confidence**: Tag background `#ECFDF3`, border `1px solid #ABEFC6`, dot `#12B76A`, text `#027A48` ("High").
- **Medium Confidence**: Tag background `#FEF0C7`, border `1px solid #FEDF89`, dot `#F79009`, text `#B54708` ("Medium").
- **Low Confidence**: Tag background `#FEF3F2`, border `1px solid #FECDCA`, dot `#F04438`, text `#B42318` ("Low").

### Data Tables
- Row height: `40px` default for dense inspection; `48px` relaxed.
- Header: Background `#F9FAFB`, text `#475467`, 12px uppercase semi-bold, border-bottom `1px solid #E4E7EC`.
- Body Rows: Background `#FFFFFF`, border-bottom `1px solid #F2F4F7`, text `#101828`. Hover: `#F8F9FA`.
- Numerical & ID values: Rendered with monospaced tabular numerals.

### Form Inputs & Filters
- Background `#FFFFFF`, height `36px`, border `1px solid #D0D5DD`, radius `6px`, text `#101828`, placeholder `#667085`.
- Active focus: Border `#0B6E66`, outline `1px solid #0B6E66`.

### Cards & Record Panels
- Background `#FFFFFF`, border `1px solid #E4E7EC`, radius `12px`, zero shadow.
- Header divided by `1px solid #F2F4F7`, padding `16px 20px`. Body padding `20px`.

### Match Confidence Score Meters
- Composed of an `IBM Plex Mono` score readout (`0.98`) followed by a horizontal progress bar.
- Track height: `6px`, background `#EAECF0`, radius `3px`.
- Fill: `#0B6E66` (for scores ≥ 0.85), `#F79009` (0.60–0.84), `#F04438` (< 0.60).