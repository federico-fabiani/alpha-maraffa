---
name: fe-debug-desktop-mobile
description: 'Debug frontend locale with desktop vs mobile landscape comparison, responsive regression checks, screenshots, and focused console/network signals. Use when inspecting layout breakage, overflow, clipping, hidden CTA, z-index issues, unreadable text, broken overlays, or mobile landscape problems on http://localhost:5173/.'
argument-hint: 'Optional: route, screen, or specific UI problem to inspect'
---

# Frontend Desktop vs Mobile Landscape Debug

Use this skill to inspect the local frontend on `http://localhost:5173/` and compare desktop against mobile landscape with concrete, visual findings only.

## When To Use

- The user asks to debug the frontend locally.
- The user mentions responsive issues, mobile bugs, layout regressions, or broken UI.
- The user asks for screenshots, desktop vs mobile comparison, or landscape validation.
- The user mentions overflow, clipping, hidden actions, bad tap targets, broken modal/overlay layering, or visual instability.

If the user says only `mobile`, assume mobile landscape.

## Required Workflow

1. Open `http://localhost:5173/` with DevTools/browser tools.
2. If the page does not load or is unreachable, stop and report the exact blocker.
3. Run a desktop check with viewport `1440x1024`.
4. Run a mobile landscape check with viewport `844x390,mobile,touch,landscape` unless the user specifies another mobile landscape target.
5. For each viewport:
   - wait for rendering to stabilize
   - capture at least one useful screenshot
   - inspect horizontal overflow, clipped content, off-viewport elements, hidden CTA, wrong stacking, tiny text, narrow tap targets, distorted images, broken modals/overlays, and fixed or sticky elements covering content
   - collect only console or network signals that are relevant to what is visibly wrong
6. If the user points to a route or feature, traverse only the minimum flow needed to reach that screen.
7. Compare desktop and mobile landscape and report only concrete, reproducible, visible issues.

## Decision Rules

- If no specific route or feature is provided, inspect the default screen at the root URL.
- If the issue is already visible on desktop, still run the mobile landscape pass and explain whether it worsens, stays the same, or changes shape.
- If console or network noise is unrelated to the observed UI problem, ignore it.
- Do not turn the task into a generic audit. Stay focused on layout, readability, interaction, and visual stability.
- Do not modify code unless the user explicitly asks for fixes.

## Output Format

Structure the result with these sections:

- `Desktop`: brief status and concrete issues found
- `Mobile landscape`: brief status and concrete issues found
- `Delta responsive`: what gets worse or breaks when moving from desktop to mobile landscape
- `Screenshot`: summary of screenshots captured
- `Console/network`: only useful signals tied to the visible problem
- `Fix consigliati`: maximum 3 fixes, ordered by impact

## Completion Criteria

The task is complete only when:

- both desktop and mobile landscape were inspected
- at least one useful screenshot per inspected state was captured
- findings are visual and reproducible, not speculative
- the desktop/mobile delta is explicit
- only relevant console/network signals are included
