---
name: Sentinel-TxM Design System
colors:
  primary: "#0071e3"       # Electric Blue (Primary Action / Selected)
  secondary: "#86868b"     # Muted gray (Labels / Secondary text)
  danger: "#ff453a"        # Warning Red (Mule Hubs / Critical Risk)
  warning: "#ff9f0a"       # Alert Orange (Structuring / Moderate Risk)
  success: "#30d158"       # Success Green (Sink Nodes / Operational status)
  background: "#0d0e12"    # Deep Charcoal background
  surface: "#16171d"       # Elevated Card/Panel background
  border: "rgba(255, 255, 255, 0.06)"  # Translucent divider border
typography:
  fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
  headline-display:
    fontSize: "36px"
    fontWeight: 700
    lineHeight: 1.1
  headline-lg:
    fontSize: "24px"
    fontWeight: 600
    lineHeight: 1.2
  headline-md:
    fontSize: "16px"
    fontWeight: 600
    lineHeight: 1.3
  body-md:
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
  label-sm:
    fontSize: "11px"
    fontWeight: 500
    letterSpacing: "0.1em"
rounded:
  sm: "6px"
  md: "12px"
  lg: "16px"
  full: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
---

# Sentinel-TxM Design Specification

## Overview
A high-fidelity, analyst-focused compliance dashboard designed with a dark, Linear-style aesthetic. It prioritizes clarity, data-density balance, and immediate highlighting of suspicious entities.

* **DESIGN_VARIANCE:** 6 (Balanced, clean layouts with structured asymmetries)
* **MOTION_INTENSITY:** 5 (Functional, smooth transitions for details and graphs)
* **VISUAL_DENSITY:** 4 (Spacious but data-rich compliance workspace)

## Colors
* **Primary (#0071e3):** Used for main interactions, active selections, and highlight states.
* **Danger (#ff453a):** Used for Mule Hubs, high-risk flags, and credit/debit indicators.
* **Warning (#ff9f0a):** Used for structuring loops and moderate-risk items.
* **Success (#30d158):** Used for Sink Nodes and operational indicators.
* **Neutrals:** Dark gray surfaces (`#16171d`) overlaying a deep Charcoal backdrop (`#0d0e12`).

## Typography
Clean system sans-serif family, favoring flat weights with high-contrast size ratios for clear data scanning. Monospace used exclusively for addresses, IDs, and financial ledgers.

## Layout
* Views are divided into distinct elevated panels with consistent gaps.
* Padding scales from 16px to 24px internally.

## Shapes
* Rounded corners applied consistently using `rounded.md` (12px) for cards, select pills, and list items.
* Interactive controls like CTAs and inputs use `rounded.sm` or `rounded.full`.

## Components
* **Card Containers:** Glassmorphic panel with `#16171d` background, thin semi-translucent borders, and soft ambient drop shadow.
* **Badges:** Semitransparent colored chip overlays matching risk status.
* **Visualizers:** Clean charts and SVG graph representations utilizing standard color codes.

## Do's and Don'ts
* **Do** highlight the Mule Hub in danger red (#ff453a) and the Sink in success green (#30d158) in the network graph.
* **Do** use custom SVG node shapes or rings to distinguish user types in the visualizer.
* **Don't** add random purple highlights or gradients (adheres to the Lila ban).
* **Do** ensure all metric cards list values clearly with concise subtitles.
