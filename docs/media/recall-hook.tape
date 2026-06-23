# vhs tape — reproducible animated capture of the recall hook firing.
# Requires: vhs (https://github.com/charmbracelet/vhs), a Personal OS install with the
# index built (qmd update && qmd embed) and the example lessons seeded.
# Run:  vhs docs/media/recall-hook.tape   ->  produces recall-hook.gif
#
# It pipes a sample prompt through the REAL UserPromptSubmit hook and prints the
# context block it injects — no mock-up, this is the actual output.

Output recall-hook.gif
Set Shell "bash"
Set FontSize 15
Set Width 1120
Set Height 480
Set Padding 18
Set Theme "Catppuccin Mocha"

Type "# What the UserPromptSubmit hook injects, on a real prompt:"
Enter
Sleep 900ms
Type `echo '{"prompt":"help me git push --force to clean up these old branches"}' | PERSONAL_OS_LANG=en python3 ~/.claude/hooks/recall-lessons.py | python3 -c 'import json,sys;print(json.load(sys.stdin)["hookSpecificOutput"]["additionalContext"])'`
Enter
Sleep 4s
