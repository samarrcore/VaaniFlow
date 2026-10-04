---
name: streamlit-ui-craft
description: Craft distinctive, production-grade UI for Streamlit apps that escapes Streamlit's generic default look. Use this skill whenever the user is building, styling, theming, or "making nicer" a Streamlit app, dashboard, or data app — even if they don't explicitly say "design." Triggers include mentions of Streamlit theming, config.toml, st.markdown CSS injection, custom components, components.html, "my Streamlit app looks generic/bland," or any request to apply real frontend design quality to something rendered in Streamlit. This skill adapts professional frontend-design methodology to Streamlit's specific constraints (Streamlit owns the DOM) and routes each aesthetic decision through the right escape hatch.
license: Adapts methodology from the frontend-design skill.
---

# Streamlit UI Craft

Streamlit is built for speed, not distinctiveness. Its defaults — system sans-serif font, flat backgrounds, symmetric column grids, a stock red accent — are precisely the "generic AI slop" aesthetic that good design avoids. The problem: you cannot style Streamlit the way you'd style a normal web page, because **Streamlit owns the DOM**. You call `st.button()` and Streamlit decides what HTML and CSS it emits.

This skill resolves that tension. It applies real frontend-design methodology to Streamlit by separating two layers:

1. **Design methodology** — the thinking process (purpose, tone, differentiation). This transfers to Streamlit with zero friction.
2. **Aesthetic levers** — typography, color, motion, spatial composition, backgrounds. These transfer with *varying* friction depending on which Streamlit escape hatch carries them.

The core skill is knowing which lever to route through which hatch, so you spend effort where it actually lands instead of fighting Streamlit's chrome.

## Step 1: Run the design-thinking process (always)

Before writing any code, commit to a direction. This is framework-agnostic and applies fully:

- **Purpose**: What does this app do? Who uses it? A FinOps dashboard for engineers and a public-facing data story want opposite treatments.
- **Tone**: Pick an *extreme* and commit. For data apps, the strongest fits are usually `editorial/magazine`, `industrial/utilitarian`, `brutalist/raw`, `luxury/refined`, or `retro-futuristic/terminal`. Avoid the timid middle.
- **Differentiation**: What is the ONE thing someone remembers? A signature hero, a distinctive type pairing, a single bold data visualization. This is where you'll spend your expensive levers (see Step 3).

Intentionality matters more than intensity. A precise, restrained design beats a busy one. Commit to the vision, then match implementation effort to it.

**Critical content rule, inherited from frontend-design:** never produce generic AI aesthetics. No Inter / Roboto / Arial / system fonts. No purple-gradient-on-white. No predictable cookie-cutter layouts. Streamlit's defaults violate all of these, so your job is active correction, not decoration.

## Step 2: Understand what you can and cannot control

Streamlit gives you escape hatches of increasing power and increasing effort. Know them before you choose levers:

| Hatch | Power | Effort | What it controls |
|-------|-------|--------|------------------|
| `config.toml` `[theme]` | Low | Trivial | Global color palette + base font. The sanctioned, upgrade-safe API. |
| Injected CSS via `st.markdown(..., unsafe_allow_html=True)` | Medium | Low | Restyles native widgets by targeting Streamlit's internal classes. Powerful but **fragile** — class names are not a stable public API. |
| Raw HTML blocks via `st.markdown` / `st.html` | Medium | Low | Fully designed *static* regions (hero, cards, banners). No Python interactivity. |
| `components.html()` | High | Medium | A sandboxed iframe running ANY HTML/CSS/JS. Full design control, static or self-contained-interactive. |
| Custom bidirectional component | Full | High | Your own frontend (incl. React) with a data bridge back to Python via `Streamlit.setComponentValue()`. The skill applies in full here. |

A key consequence: **Streamlit's own chrome (native widgets, layout flow) can be themed and lightly restyled, but never fully redesigned.** Deep design always lives inside an HTML block or component you author.

## Step 3: Route each aesthetic lever through the right hatch

This is the heart of the skill. Each lever from frontend-design has a different transfer-friction in Streamlit. Rank by friction and spend accordingly — cheap levers globally, expensive levers only on your differentiating surface.

**Color & Theme — nearly free. Do it globally.**
`config.toml` theming is purpose-built for this. Express a real palette (dominant color + sharp accent, not a timid even spread) through `primaryColor`, `backgroundColor`, `secondaryBackgroundColor`, `textColor`. This is the single highest-leverage move and it's upgrade-safe.

**Body typography — nearly free. Do it globally.**
Set the base font in `config.toml`. For a non-system font, `@import` it via a small injected-CSS block. Replacing Streamlit's default system sans is the second-highest-leverage move because type is the most pervasive signal of "designed vs. default."

**Display typography — cheap. Use HTML blocks.**
Headers, hero text, and section titles can carry a distinctive display font inside `st.markdown`/`st.html` blocks. Pair a characterful display face with the refined body face you set globally.

**Motion — cheap inside blocks, awkward natively.**
The rerun model fights animation on native widgets, and you don't own those elements. But CSS animation inside an HTML block or component works fine. Favor ONE well-orchestrated load with staggered reveals (`animation-delay`) over scattered micro-interactions.

**Backgrounds & atmosphere — expensive. Spend deliberately.**
Gradient meshes, noise/grain, dramatic shadows, layered transparency, decorative borders. These do NOT apply convincingly to Streamlit's chrome. Accept flat native chrome and concentrate atmosphere inside `components.html` regions you author.

**Spatial composition — most expensive. Component-only.**
Asymmetry, overlap, diagonal flow, grid-breaking. Streamlit's `st.columns`/`st.container` produce conventional symmetric flow and resist this. You get real spatial freedom only inside a component's iframe. If grid-breaking is your differentiator, it MUST live in a component.

### The design-budget heuristic

Putting it together: apply methodology globally, then —
- **Free/cheap levers (color, body+display type, motion):** apply broadly across the whole app.
- **Expensive levers (atmosphere, spatial composition):** spend only on the one or two high-visibility surfaces that carry your "unforgettable" element.

This aligns with frontend-design's own advice to concentrate high-impact effort on memorable moments. Let native widgets stay utilitarian for routine inputs; pour full design treatment into the hero or signature data-card.

## Step 4: Implement

Produce concrete deliverables, not advice. A typical complete answer includes:

1. A `.streamlit/config.toml` `[theme]` block encoding the palette + base font.
2. A reusable injected-CSS function (e.g. `inject_css()`) for font imports and tasteful native-widget restyling — with a comment noting class-name fragility.
3. One or more `components.html()` blocks (or a full custom component) for the differentiating surfaces, carrying the expensive levers.
4. Python glue showing how it fits a real Streamlit script.

For implementation detail, syntax, and copy-paste patterns, read:
- `references/streamlit-hatches.md` — exact syntax for every escape hatch, including config.toml keys, the CSS-injection pattern, `components.html` usage, and a custom bidirectional component scaffold. Read this when writing implementation code.
- `references/aesthetic-recipes.md` — worked aesthetic directions (editorial, industrial/terminal, luxury/refined, brutalist) with concrete font pairings, palettes, and Streamlit-specific notes. Read this when choosing or executing a tone in Step 1.

## Anti-patterns

- **Decorating instead of redesigning.** Tweaking the stock red accent and stopping. Commit to a full direction.
- **Fighting the chrome.** Pouring hours into CSS-hacking native widgets toward grid-breaking layouts. Move that into a component instead.
- **Spreading expensive levers thin.** Atmosphere everywhere reads as noise and breaks on upgrades. Concentrate it.
- **Relying on injected-CSS class hacks for critical UI.** They break on Streamlit version bumps. Use them for polish, not load-bearing structure.
- **Converging on the same look every time.** Vary fonts, themes (light AND dark), and aesthetic direction per project. Never default to one safe house style.
