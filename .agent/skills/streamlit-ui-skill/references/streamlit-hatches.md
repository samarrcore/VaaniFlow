# Streamlit Escape Hatches — Implementation Reference

Exact syntax for every mechanism the skill routes levers through. Ordered from lowest effort / lowest power to highest.

## Table of contents
1. config.toml theming
2. Injected CSS (font import + native widget restyle)
3. Raw HTML blocks
4. components.html (self-contained iframe)
5. Custom bidirectional component (full control)
6. The rerun model and what it means for styling

---

## 1. config.toml theming

The sanctioned, upgrade-safe way to set the global palette and base font. Lives at `.streamlit/config.toml` in the app's working directory (or `~/.streamlit/config.toml` globally).

```toml
[theme]
primaryColor = "#E8552D"            # accent: buttons, sliders, active states. Pick a SHARP accent.
backgroundColor = "#0E1117"         # main canvas
secondaryBackgroundColor = "#1A1D26" # sidebar, widget fills, st.container surfaces
textColor = "#EAEAEA"
font = "serif"                       # "sans serif" | "serif" | "monospace"
```

Notes:
- `font` only accepts the three generic families. To use a *specific* font (e.g. a Google Font), set the closest generic here AND override via injected CSS (section 2).
- Newer Streamlit versions support more theme keys (e.g. `baseFontSize`, `borderColor`, heading fonts). Verify against the installed version before relying on them — when unsure, treat only the five keys above as universally safe and do the rest in CSS.
- This is the highest-leverage, lowest-risk move. Always start here.

---

## 2. Injected CSS

Restyle native widgets and import fonts by pushing raw CSS into the page. Wrap in a function and call once near the top of the script.

```python
import streamlit as st

def inject_css():
    st.markdown("""
    <style>
    /* Font import — this is how you get a non-system font */
    @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600&family=Space+Mono&display=swap');

    /* Global type. [data-testid="stAppViewContainer"] is the app root. */
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Fraunces', Georgia, serif;
    }

    /* Restyle the native button. .stButton is an internal class — see fragility note. */
    .stButton > button {
        border-radius: 2px;
        border: 1px solid #E8552D;
        background: transparent;
        color: #E8552D;
        font-family: 'Space Mono', monospace;
        letter-spacing: 0.05em;
        transition: all 0.18s ease;
    }
    .stButton > button:hover {
        background: #E8552D;
        color: #0E1117;
    }

    /* Hide Streamlit's default chrome for a cleaner canvas (optional) */
    #MainMenu, footer, header { visibility: hidden; }
    </style>
    """, unsafe_allow_html=True)

inject_css()
```

**Fragility note — state this to the user.** Selectors like `.stButton`, `[data-testid="stAppViewContainer"]`, `[data-testid="stSidebar"]` target Streamlit's internal DOM, which is NOT a stable public API. They can change on version upgrades. Use injected CSS for *polish* (color, type, spacing, hover), not for load-bearing structure. Pin your Streamlit version if you depend on specific selectors.

Useful stable-ish testids (verify per version): `stAppViewContainer`, `stSidebar`, `stHeader`, `stToolbar`, `stMetric`, `stDataFrame`.

---

## 3. Raw HTML blocks

For fully designed *static* regions. Two routes:

```python
# Modern, preferred: st.html (auto-sanitizes less aggressively, purpose-built)
st.html("""
<div class="hero">
  <h1>Quarterly Signal</h1>
  <p>Cloud spend, decomposed.</p>
</div>
<style>
.hero { padding: 4rem 0; border-bottom: 1px solid #E8552D; }
.hero h1 { font-family: 'Fraunces', serif; font-size: 4rem; margin: 0; }
</style>
""")

# Older route: st.markdown with unsafe_allow_html
st.markdown("<div class='hero'>...</div>", unsafe_allow_html=True)
```

Limitation: no Python interactivity. Buttons/inputs here don't talk back to your script. For that, use a component (sections 4–5). Good for heroes, banners, custom cards, section dividers, footers.

---

## 4. components.html (self-contained iframe)

Renders arbitrary HTML/CSS/JS in a sandboxed iframe. This is where expensive levers (atmosphere, spatial composition, motion) get full freedom. The iframe is isolated, so your CSS can't leak into — or be broken by — Streamlit's chrome.

```python
import streamlit.components.v1 as components

components.html("""
<div id="card">
  <canvas id="mesh"></canvas>
  <div class="content">
    <span class="label">MOTION HEALTH</span>
    <span class="value">59%</span>
  </div>
</div>
<style>
  #card { position: relative; height: 220px; border-radius: 6px; overflow: hidden;
          font-family: 'Space Mono', monospace; background: #0E1117; }
  #mesh { position: absolute; inset: 0; }              /* gradient mesh layer */
  .content { position: relative; padding: 2rem; }       /* overlap: content over mesh */
  .value { font-size: 3.5rem; color: #E8552D; display:block;
           animation: rise 0.8s cubic-bezier(.2,.8,.2,1) both; animation-delay: .2s; }
  @keyframes rise { from { opacity:0; transform: translateY(12px);} to {opacity:1; transform:none;} }
</style>
<script>
  // self-contained JS is fine here — e.g. animate the canvas mesh
</script>
""", height=240, scrolling=False)
```

Key params: `height` (required — iframe won't auto-size, set it explicitly), `scrolling`, `width`. Because it's an iframe, you must inline everything (fonts via `@import`, all CSS, all JS). It cannot read your Python variables except what you interpolate into the string before sending.

---

## 5. Custom bidirectional component

When you need your designed frontend to send values BACK to Python (a custom input, an interactive chart that reports selections). Two modes:

**Quick mode (no separate build):** use `components.html` and `Streamlit.setComponentValue()` — but note the value only returns when declared via `declare_component`. For true bidirectional flow you generally need the declared-component pattern below.

**Declared component (full):**

```python
import streamlit.components.v1 as components

# Point at a directory containing your built frontend (index.html + assets),
# or a dev server URL during development.
_component = components.declare_component(
    "designed_input",
    path="./frontend/build",   # or: url="http://localhost:3001"
)

def designed_input(label, default=None, key=None):
    return _component(label=label, default=default, key=key)

# Usage in the app — behaves like a native widget, returns on rerun:
value = designed_input("Pick a region", default="us-central1")
st.write("You chose:", value)
```

On the frontend side, the contract is: receive args via the `Streamlit.RENDER_EVENT`, call `Streamlit.setComponentValue(x)` to push values back, and call `Streamlit.setFrameHeight()` after layout. A React template ships via `npx create-streamlit-component` style scaffolds, or you can hand-roll a vanilla `index.html` that loads `streamlit-component-lib`. This is the only hatch where the full frontend-design skill (including React + Motion) applies verbatim.

When recommending this, flag the cost honestly: it needs a separate frontend build step and toolchain. Justify it only for the differentiating surface, not routine inputs.

---

## 6. The rerun model and what it means for styling

Streamlit reruns the whole script top-to-bottom on every interaction. Implications for UI work:

- **Call `inject_css()` once at the top.** It re-runs each time, which is fine (idempotent), but keep it early so styles apply before content renders.
- **Animations on native widgets restart on rerun.** This is why motion belongs in iframes/components, which aren't torn down the same way.
- **Don't store design state in globals.** Use `st.session_state` if a styled component needs to remember anything across reruns.
- **`@st.cache_data` / `@st.cache_resource`** matter for performance but are orthogonal to styling — don't cache the CSS injection, it's cheap.
