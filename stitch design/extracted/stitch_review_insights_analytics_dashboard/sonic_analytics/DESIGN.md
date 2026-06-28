---
name: Sonic Analytics
colors:
  surface: '#121414'
  surface-dim: '#121414'
  surface-bright: '#38393a'
  surface-container-lowest: '#0d0e0f'
  surface-container-low: '#1a1c1c'
  surface-container: '#1e2020'
  surface-container-high: '#292a2a'
  surface-container-highest: '#343535'
  on-surface: '#e3e2e2'
  on-surface-variant: '#bccbb9'
  inverse-surface: '#e3e2e2'
  inverse-on-surface: '#2f3131'
  outline: '#869585'
  outline-variant: '#3d4a3d'
  surface-tint: '#53e076'
  primary: '#53e076'
  on-primary: '#003914'
  primary-container: '#1db954'
  on-primary-container: '#004118'
  inverse-primary: '#006e2d'
  secondary: '#c8c6c5'
  on-secondary: '#313030'
  secondary-container: '#4a4949'
  on-secondary-container: '#bab8b7'
  tertiary: '#c8c6c5'
  on-tertiary: '#303030'
  tertiary-container: '#a2a1a0'
  on-tertiary-container: '#383838'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#72fe8f'
  primary-fixed-dim: '#53e076'
  on-primary-fixed: '#002108'
  on-primary-fixed-variant: '#005320'
  secondary-fixed: '#e5e2e1'
  secondary-fixed-dim: '#c8c6c5'
  on-secondary-fixed: '#1c1b1b'
  on-secondary-fixed-variant: '#474646'
  tertiary-fixed: '#e4e2e1'
  tertiary-fixed-dim: '#c8c6c5'
  on-tertiary-fixed: '#1b1c1c'
  on-tertiary-fixed-variant: '#474746'
  background: '#121414'
  on-background: '#e3e2e2'
  surface-variant: '#343535'
typography:
  display-lg:
    fontFamily: Montserrat
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.04em
  headline-lg:
    fontFamily: Montserrat
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.03em
  headline-md:
    fontFamily: Montserrat
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
    letterSpacing: -0.02em
  headline-sm:
    fontFamily: Montserrat
    fontSize: 18px
    fontWeight: '700'
    lineHeight: 24px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Montserrat
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
    letterSpacing: -0.01em
  body-md:
    fontFamily: Montserrat
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: 0em
  label-md:
    fontFamily: Montserrat
    fontSize: 12px
    fontWeight: '700'
    lineHeight: 16px
    letterSpacing: 0.05em
  label-sm:
    fontFamily: Montserrat
    fontSize: 11px
    fontWeight: '400'
    lineHeight: 14px
    letterSpacing: 0em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  sidebar-width: 250px
  topbar-height: 64px
  gutter: 24px
  card-gap: 16px
  container-padding: 32px
---

## Brand & Style
The design system is engineered to emulate the immersive, high-contrast, and "content-first" aesthetic of the world's leading music streaming platforms. It targets data analysts and brand managers who require a high-density information environment that feels premium and effortless rather than clinical.

The visual style is a blend of **Modern Minimalism** and **Tonal Layering**. By utilizing a pitch-black foundation, we create a void where data visualizations and key metrics "pop" with vibrant clarity. The interface avoids traditional skeuomorphism and heavy borders, relying instead on changes in surface luminosity and the strategic application of "Spotify Green" to guide user attention and signal interactivity.

## Colors
The palette is rooted in true black (`#000000`) to maximize OLED efficiency and visual depth. 

- **Primary:** The iconic green is used exclusively for primary actions, success states, and active toggle markers.
- **Surface Architecture:** We use `#121212` for primary containers (sidebar, cards) and `#282828` for hover states and secondary UI elements like progress bar backgrounds.
- **Typography:** Contrast is strictly managed. `#FFFFFF` is reserved for critical headers and active states, while `#B3B3B3` is used for all secondary metadata and body text to reduce eye strain in dark environments.

## Typography
The system uses **Montserrat** to achieve a clean, geometric look that remains highly legible at small sizes. 

Key typographic rules:
- **Weight:** Bold (700) is used aggressively for headers and metrics to create a clear information hierarchy against the dark background.
- **Spacing:** Headlines use negative letter spacing to create a tight, professional editorial feel. Labels use increased letter spacing and uppercase styling for "overline" category descriptions.
- **Hierarchy:** Metrics (big numbers) should utilize `display-lg` to command attention.

## Layout & Spacing
The layout follows a **Hybrid Grid** model optimized for dashboard density.

1.  **Sidebar:** A fixed 250px left-hand navigation anchored to the viewport. It uses `#121212` to subtly separate it from the main canvas.
2.  **Main Content:** A fluid canvas that stretches to fill the remaining width. It utilizes a 12-column grid system for card placement.
3.  **Sticky Top Bar:** A semi-transparent (`rgba(0,0,0,0.7)`) header with a backdrop-blur effect that persists during scroll.
4.  **Rhythm:** An 8px linear scale governs all padding and margins. 24px is the standard gutter between major layout blocks, while 16px is used for internal card spacing.

## Elevation & Depth
Depth is conveyed through **Tonal Layering** rather than traditional drop shadows. In this system, "higher" elements are represented by lighter shades of grey.

- **Level 0 (Base):** `#000000` — The main application background.
- **Level 1 (Surface):** `#121212` — Sidebars, footer players, and primary data cards.
- **Level 2 (Interaction):** `#282828` — Hover states for list items and buttons.
- **Level 3 (Overlay):** `#3E3E3E` — Tooltips and dropdown menus.

No borders are used. Separation is achieved purely through the contrast between these tonal steps.

## Shapes
The shape language is "Softly Geometric." 

- **Cards & Containers:** Use a consistent 8px radius (`rounded-md/lg`) to provide a modern, approachable feel that isn't overly organic.
- **Interactive Elements:** Buttons and Chips utilize a higher radius (up to 32px or full pill-shape) to distinguish them from structural containers.
- **Avatars:** User and Brand profile images are strictly circular.

## Components

### Buttons
- **Primary:** Pill-shaped, background `#1DB954`, text `#000000` (Bold). On hover, scale slightly (1.04x) and increase brightness.
- **Secondary:** Pill-shaped, transparent background with a white outline (1px) or solid `#FFFFFF` with black text.
- **Ghost:** No background or border. Text color `#B3B3B3` turning `#FFFFFF` on hover.

### Cards
- **Stat Cards:** Background `#121212`, 8px radius, no border. Padding: 24px.
- **Hover State:** Background shifts to `#1a1a1a` or `#282828` smoothly (transition: 200ms).

### Data Lists
- **Rows:** Transparent background. On hover, background becomes `#282828` with an 4px border-radius applied to the row highlight.
- **Dividers:** Use sparingly. When needed, use `#282828` at 1px thickness.

### Input Fields
- **Search:** Rounded pill-shape, background `#242424`, placeholder text `#757575`. No border. On focus, background becomes `#2a2a2a`.

### Progress & Sentiment Bars
- **Track:** `#4d4d4d` background.
- **Indicator:** `#1DB954` (or secondary accent for specific sentiment like red/yellow). Height should be 4px-6px with rounded caps.