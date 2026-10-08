# Google Stitch prompts for Lumina

Use these at https://stitch.withgoogle.com to explore alternative layouts. Paste the **design brief** first, then one screen prompt at a time. If a result is worth keeping, export its HTML/CSS and hand it to the team: we copy the ideas into our React components and keep our own design tokens (`frontend/src/styles/tokens.css`), so the app stays consistent.

## Design brief (paste this first, every time)

> Desktop web app for a bank's data team, called Lumina. It merges customer records from several bank systems into one trusted "golden record" per customer and gives each customer a trust score from 0 to 1.
> Users are data stewards, compliance officers and relationship managers. They work in it all day, so it must be calm, dense and fast to scan, not decorative.
> Style: enterprise fintech, like Stripe Dashboard or Linear. Light theme with a dark-mode variant. Background #F6F7F9, white cards with 1px #E4E7EC borders and 12px radius, no drop shadows on cards. One accent colour, deep teal #0B6E66, used only for primary actions, the active nav item and data bars. Status colours only for status, always with a dot and a word: green "High", amber "Medium", red "Low".
> Type: IBM Plex Sans, 14px body, 22px page titles, IBM Plex Mono with tabular numbers for scores and IDs.
> Layout: 248px white left sidebar with logo, grouped navigation (Workspace: Overview, Customers, Match review with a count badge; Data: Connectors) and the signed-in user at the bottom. Content max width 1280px with 32px padding.
> No gradients, no stock illustrations, no emoji, no 3D, no glassmorphism.

## Screen prompts

### Overview

> Overview dashboard. Page title "Overview" with subtitle "How reliable your customer data is right now. Last sync 13 min ago."
> A row of 4 KPI cards: Customers 19 (built from 24 source records); Average trust 0.64 with a small horizontal meter; Low trust 9 (0 medium, 10 high), clickable; Matches to review 5, clickable.
> Below, a two-column row: left (2/3 width) a column chart "Trust score distribution", customers per 0.1 of trust score from 0.0 to 1.0, single teal colour, dashed reference lines at 0.6 labelled Medium and 0.8 labelled High. Right (1/3) a "Sources" table: Oracle FLEXCUBE trust 0.85, 10 records; Salesforce 0.55, 8; Branch Uploads 0.40, 6; each with "Synced 1 h ago".
> Bottom: "Lowest trust customers" table with avatar initials, name, ID like C-10015, trust meter with score and a red "Low" badge, source chips, and "fields to review".

### Customers list

> Customers list page. Toolbar: search field with a magnifier ("Search name or ID, e.g. C-10001"), a segmented control All / Low / Medium / High, and a sort dropdown "Lowest trust first".
> Table columns: Customer (round avatar with initials, name, monospace ID below), Trust score (small meter, score like 0.34, status badge), Found in (small grey chips: FLEXCUBE, Salesforce, Branch upload), Conflicts (number, right aligned), Review (red badge "5 fields" or green "Complete"), Updated ("13 min ago"). Whole row is clickable. Footer shows "19 customers".

### Customer profile

> Customer profile page. Breadcrumb "Customers > C-10001", title "Customer profile".
> Header card: large avatar "SK", name "Suresh Kumar", "C-10001 · Found in 3 sources", source chips. On the right a 48px hero number "0.85" with a green "High" badge and "Recalculated 13 min ago".
> Two columns. Left: "Golden record" card, a list of fields (Name, Mobile, Email, Address, Date of birth); each row shows the chosen value, a small grey line "Oracle FLEXCUBE · trust 0.85 · updated 2 Nov 2025", and on the right an amber badge "2 other values" or a green "Agreed".
> Right: "Why this score" card. For each field a horizontal bar: light teal track whose length is the field's weight (0.25, 0.25, 0.15, 0.20, 0.15) and a solid teal fill for what it contributes (weight x source trust), with "0.21 / 0.25" on the right. Total row "Trust score 0.85".
> Bottom: "What each source says" table, one row per source system, columns for each field; the cells used in the golden record are tinted pale teal.

### Match review

> Match review page. Intro text explaining these records look like the same person but need a human decision. Segmented control: To review / Merged / Kept apart.
> A stack of cards, one per possible duplicate. Card header: "Anita Deshmukh and Anita S Deshmukh", subtitle "Match score 57 · same dob, name 93%", amber badge "Needs decision".
> Card body: a 4-column comparison table: Field | Oracle FLEXCUBE · C-10002 | a small round icon (green check if equal, amber not-equal sign if different, grey dash if missing) | Branch Uploads · C-10015.
> Card footer: hint text on the left; on the right a secondary button "Different people" with an X icon and a primary teal button "Merge records".

### Connectors

> Connectors page: a grid of cards, one per bank system. Each card: square icon (database for core banking, cloud for CRM, document for files), name "Oracle FLEXCUBE", category "Core banking", green "Connected" badge. A 3-cell stats strip: Trust 0.85, Records 10, Last sync 1 h ago. Actions: primary "Sync now" with a refresh icon, secondary "Disconnect" with a power icon. A disconnected card has a dashed border and faded content.

### Login

> Centered sign-in card on a light grey background: Lumina logo mark (teal rounded square) with "Lumina / Customer data platform", heading "Sign in", helper text, Username and Password fields, full-width teal "Sign in" button, and a small shield icon line "Access is limited to authorised bank staff."
