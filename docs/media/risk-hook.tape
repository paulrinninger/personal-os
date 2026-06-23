# vhs tape — reproducible animated capture of the risk hook firing.
# Requires: vhs (https://github.com/charmbracelet/vhs), a Personal OS install with the
# index built (qmd update && qmd embed) and the example lessons seeded.
# Run:  vhs docs/media/risk-hook.tape   ->  produces risk-hook.gif
#
# It pipes a risky tool call through the REAL PreToolUse hook and prints the context
# block it injects at the action moment — the actual output, not a mock-up.

Output risk-hook.gif
Set Shell "bash"
Set FontSize 15
Set Width 1120
Set Height 480
Set Padding 18
Set Theme "Catppuccin Mocha"

Type "# What the PreToolUse hook injects right before 'git push --force':"
Enter
Sleep 900ms
Type `echo '{"tool_name":"Bash","tool_input":{"command":"git push --force origin main"}}' | PERSONAL_OS_LANG=en python3 ~/.claude/hooks/risk-recall.py | python3 -c 'import json,sys;print(json.load(sys.stdin)["hookSpecificOutput"]["additionalContext"])'`
Enter
Sleep 4s
