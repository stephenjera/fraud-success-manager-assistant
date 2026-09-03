# Diagrams — stub

**Status:** stub. No Excalidraw source files exist in this folder yet.

This is not a missing-files situation; it's ADR-0010 in action. A
diagram here must map **1:1** to an `../architecture/*.md` doc that (a)
has been discussed and (b) has a decision behind it where it's a choice.
No doc, no diagram.

When the folder fills in, the expected layout is:

```
diagrams/
├── context.excalidraw            # ↔ ../architecture/context.md
├── context.svg                   # committed export for PR diffs
├── components.excalidraw
├── components.svg
├── agent-loop.excalidraw
├── agent-loop.svg
├── rule-lifecycle.excalidraw
├── rule-lifecycle.svg
├── data-model.excalidraw
├── data-model.svg
├── api-sequence.excalidraw       # ↔ ../architecture/api-contract.md
├── api-sequence.svg
├── deploy.excalidraw
├── deploy.svg
└── eval.excalidraw               # ↔ ../architecture/eval-design.md
    └── eval.svg
```

**The UX wireframes are not here — they are `../ux/wireframes.html`.**
Decided 2026-09-02: a three-pane wireframe is spatial (left→center→right)
and the Excalidraw MCP lays it out as a containment hierarchy instead, so
the frames are minimal HTML in `../ux/` (one file, no build, opens in any
browser). See the note in `../ux/wireframes.md` for the decision and the
coverage check it carries.

Rules (from ADR-0010, applied here):

- **Each file maps to one doc.** No diagram that doesn't trace to a
  doc, no doc whose content is "look at the diagram."
- **Each has a `.svg` committed alongside it.** The `.excalidraw` is
  source (editable in the excalidraw app); the `.svg` is what makes a
  diagram change show as a reviewable diff in a PR instead of "trust me,
  open the file."
- **A diagram is redrawn when its decision changes, not patched.** The
  file *is* the decision's rendering; a redline to a diagram means the
  decision changed and the doc should change in the same PR.

Out of scope for this folder: `*.png`, `*.html`, any binary form other
than Excalidraw + SVG. The point is reviewability, not portability.
