# Aesthetic Recipes for Streamlit

Worked design directions, each with a font pairing, palette, and Streamlit-specific routing notes. These are starting points to adapt — not house styles to copy verbatim. Vary your choice per project; never converge on one default. Each recipe names which levers to apply globally (cheap) and which to reserve for the differentiating surface (expensive).

For exact syntax of every mechanism referenced here, see `streamlit-hatches.md`.

## How to use a recipe
1. In design-thinking (Step 1), pick the direction that fits the app's purpose and audience.
2. Translate the palette into a `config.toml` `[theme]` block.
3. Import the fonts via injected CSS; set body font globally, display font in HTML blocks.
4. Build the hero / signature card in `components.html` carrying the atmosphere + spatial levers.

---

## Recipe A — Editorial / Magazine
Best for: data stories, reports, public-facing dashboards, anything narrative.

- **Type pairing:** Display = `Fraunces` or `Playfair Display` (high-contrast serif). Body = `Newsreader` or `Source Serif 4`. Mono accent for labels = `Space Mono`.
- **Palette (light):** background `#FBFAF7` (warm paper), text `#1A1A1A`, accent `#B23A2E` (ink red), secondary bg `#F0EDE6`.
- **Signature move:** oversized display headline with a thin rule beneath, generous margins, drop-cap or kicker labels in mono. Asymmetric two-column intro where the headline column is wider.
- **Streamlit routing:** palette + body serif go global via config.toml + CSS import. The asymmetric headline block is an `st.html` region (static is fine for a header). Keep native charts but restyle their container padding for editorial whitespace.

## Recipe B — Industrial / Terminal
Best for: FinOps dashboards, ops monitoring, engineering-facing tools, security consoles.

- **Type pairing:** Everything mono or near-mono. Display = `JetBrains Mono` or `IBM Plex Mono` (heavier weight). Body = `IBM Plex Sans`. 
- **Palette (dark):** background `#0B0E0F`, text `#C8D0CC`, accent `#3DDC84` or amber `#E8A33D`, secondary bg `#14191B`. Thin 1px borders everywhere, `borderColor` feel.
- **Signature move:** dense data grid with hairline borders, monospace numerals (`font-variant-numeric: tabular-nums`), a "system status" header bar, subtle scanline or grid-texture background.
- **Streamlit routing:** dark palette global via config.toml. Tabular-nums and border styling via injected CSS on `stMetric`/`stDataFrame` (note fragility). Scanline/grid texture is atmosphere — put it in a `components.html` header bar, not on the chrome.

## Recipe C — Luxury / Refined
Best for: executive summaries, premium product analytics, client-facing deliverables.

- **Type pairing:** Display = `Cormorant Garamond` (light weight, large) or `Marcellus`. Body = `Outfit` or `Mona Sans` at low weight. 
- **Palette (dark):** near-black `#111014`, text `#E6E1D8`, accent gold `#C2A05A`, secondary `#1B1A20`. Restraint is the whole point.
- **Signature move:** vast negative space, one thin gold rule, slow fade-in on load (staggered `animation-delay`), letter-spaced small-caps labels. Nothing competes.
- **Streamlit routing:** palette + light-weight body font global. The hero (thin rule, large light serif, staggered fade) is a `components.html` block — the fade-in needs the iframe to survive reruns cleanly. Resist decorating native widgets; the elegance is in what you DON'T style.

## Recipe D — Brutalist / Raw
Best for: developer tools, indie products, anything that wants personality and memorability over polish.

- **Type pairing:** Display = `Archivo Black` or `Anton` (heavy grotesque). Body = `Archivo` or `Spline Sans Mono`. 
- **Palette (light, high-contrast):** background `#FFFFFF` or `#F2F0EB`, text `#000000`, accent a single loud color like `#FF4D00` or electric `#2D5BFF`. Hard black borders, visible structure.
- **Signature move:** thick borders, offset hard shadows (`box-shadow: 6px 6px 0 #000`), exposed grid, intentionally "unfinished" raw edges, no border-radius. Overlapping blocks.
- **Streamlit routing:** palette global. Button restyling (hard shadow, square corners, heavy border) via injected CSS — brutalism tolerates the fragility because the look is forgiving. Overlap and grid-breaking go in a `components.html` block; native columns can't overlap.

---

## Choosing fonts well (the highest-signal lever)
- Always pair a **distinctive display** face with a **refined body** face. Same font for both reads as default.
- Never use Inter, Roboto, Arial, Helvetica, or system-ui as the primary identity. They are the "AI slop" signal the methodology explicitly rejects.
- Mono fonts punch above their weight in data apps — they signal precision and instantly de-genericize numerals.
- Import only the weights you use (keeps the `@import` light and the app fast).

## Palette discipline
- One dominant color + one sharp accent beats five timid evenly-distributed colors.
- Decide light vs. dark deliberately per project — don't always reach for dark.
- Avoid the purple-gradient-on-white cliché entirely.
- Set all four color slots in config.toml so the WHOLE app (including sidebar and widget fills) coheres, not just the canvas.

## Motion discipline
- One orchestrated page-load reveal with staggered `animation-delay` > many scattered hovers.
- Keep motion inside HTML blocks / components so reruns don't restart it jarringly.
- Respect `prefers-reduced-motion` with a media query in your injected CSS / component styles.
