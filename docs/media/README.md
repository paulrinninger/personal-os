# Media

Visuals referenced by the README.

| File | What it is |
|------|------------|
| `recall-hook.svg` | Still showing the `UserPromptSubmit` hook injecting a lesson on every prompt. |
| `risk-hook.svg`   | Still showing the `PreToolUse` hook re-surfacing a lesson before `git push --force`. |
| `recall-hook.tape` / `risk-hook.tape` | [vhs](https://github.com/charmbracelet/vhs) scripts that pipe a sample prompt through the **real** hooks and record the actual injected output as an animated gif. |

The SVG stills render on GitHub out of the box. To produce animated gifs that match what
you'll really see (and swap them into the README), install vhs and run:

```bash
vhs docs/media/recall-hook.tape   # -> recall-hook.gif
vhs docs/media/risk-hook.tape     # -> risk-hook.gif
```

The tapes need a working install (`qmd update && qmd embed` done, example lessons seeded),
so the captured output is genuine, not staged.
