---
version: alpha
name: Samanvaya
description: Engineering-management workspace with evidence-first scoring status
colors:
  primary: '#81b3fc'
  action: '#2563eb'
  background: '#101318'
  surface: '#171b22'
  text: '#f8fafc'
  warning: '#e7b45a'
  success: '#55c69b'
typography:
  sans:
    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
  mono:
    fontFamily: "'JetBrains Mono', monospace"
rounded:
  sm: 6px
  md: 10px
  lg: 14px
  xl: 20px
spacing:
  card-padding: 1.25rem
  section-gap: 1.5rem
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
where reviewers can scan them together. Ink-toned surfaces and the existing blue
accent connect the dark and light workspaces. The sign-in preview demonstrates
this pattern with a pull request, a CI run, and a review record.

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
Status also appears as text. Charts use their own semantic series tokens and
keep their counts and state labels available.

## Typography

Use the existing sans family for controls and body copy, mono for revision IDs.
Use sentence-case labels, tabular numbers and restrained headings. No new fonts.

## Layout

Reuse the application content scroller, Card spacing and native Select owner.
Feature sections use a natural-height stack; tables own horizontal overflow.
Forms wrap to one column at narrow widths. Do not place viewport-height limits
on the shared page or clip a sibling form to fit a table.

## Elevation & Depth

Use solid card backgrounds and tonal steps for structure. Reserve elevation
for overlays and prioritize focus indicators over decorative shadows.

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
