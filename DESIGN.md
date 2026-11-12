---
version: alpha
name: Samanvaya
description: Engineering-management workspace with evidence-first scoring status
colors:
  primary: '#3b82f6'
  background: '#0a0e17'
  surface: '#111827'
  text: '#f8fafc'
  warning: '#f59e0b'
  success: '#10b981'
typography:
  sans:
    fontFamily: "'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
  mono:
    fontFamily: "'JetBrains Mono', monospace"
rounded:
  sm: 6px
  md: 10px
  lg: 14px
  xl: 20px
spacing:
  card-padding: 1.25rem
  section-gap: 1.75rem
components:
  card: {}
  button: {}
  select: {}
  textarea: {}
---

# Samanvaya Design System

## Overview

### Creative North Star

An engineering review ledger: the current decision state and its source belong
next to every number. Preserve the existing dark blue workspace; no rebrand.

### Product context and register

Engineering staff, scoped managers, HR and executives inspect evidence and
historical outcomes. This is an English product/admin surface; no Japan-market
or Japanese-locale requirement is established. Desktop review with narrow-screen
access follows the existing application shell. The signature is an explicit
legacy/provisional/approved status accompanying the score, without decorative
confidence percentages. Avoid leaderboard, competitive ranking and marketing
score treatments. The supplied scoring specification and server contracts own
authority; colors never establish approval.

Runtime tokens remain owned by [index.css](frontend/src/index.css). This file
records that existing system; it does not generate a second token implementation.

## Colors

Existing blue is interactive emphasis, amber marks pending/legacy states and
green is reserved for an actual approved result. Surface/text values mirror
the runtime dark theme; the existing light-theme adapter remains authoritative.
Status must also appear as text, not just color.

## Typography

Use the existing sans family for controls and body copy, mono for revision IDs.
Use sentence-case labels, tabular numbers and restrained headings. No new fonts.

## Layout

Reuse the application content scroller, Card spacing and native Select owner.
Feature sections use a natural-height stack; tables own horizontal overflow.
Forms wrap to one column at narrow widths. Do not place viewport-height limits
on the shared page or clip a sibling form to fit a table.

## Elevation & Depth

Reuse shared card borders and tonal backgrounds. Do not add new glass/glow or
modal layers for scoring status. Existing shell elevation remains unchanged.

## Shapes

Use the existing medium control and large card radii. No new shape language.

## Components

Card, Button, Select and Input remain shared owners. ScoreCard owns performance
number semantics; all callers supply provenance metadata. The new shared
Textarea owns labeled notes, validation and resize behavior. New scoring forms
use explicit field errors and keep notes on failed/stale submissions. Buttons
do not widen while busy. Historical unknowns are not zeros or default grades.

## Motion

Scoring status is static. Respect reduced motion; do not animate scores or
suggest a live rise/fall when comparability has not been established.

## Accessibility

Target WCAG 2.2 AA in the touched workflow: native controls, associated labels,
visible focus, text errors/live status, keyboard operation and no hidden actions.
The native select popup is platform-owned. Existing unrelated legacy UI drift
is not certified by the scoped scoring audit.
