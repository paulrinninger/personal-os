#!/usr/bin/env python3
"""Personal OS installer — wires the framework into your machine. Local & $0.

What it does (and prints the full plan BEFORE touching anything):
  1. detect OS + which of qmd / graphify / ollama are installed
  2. create your vault from the empty scaffold (default ~/vault), optionally seed examples
  3. copy commands / hooks / engine / skills into ~/.claude (WITHOUT clobbering your settings)
  4. deep-merge our hooks + env + permissions into ~/.claude/settings.json (backs up first)
  4b. materialize <state home>/guards.json from guards.example.json (author email from
      --git-author-email / config `git_author_email`; never overwrites an existing one)
  5. append the Personal OS section to ~/.claude/CLAUDE.md between sentinels (idempotent)
  6. write ~/.config/qmd/index.yml pointing at your vault, then build the first index
  7. optionally register a nightly graph rebuild (--schedule) and/or the nightly
     dreaming pass (--schedule-dream), and an opt-in vault autopush Stop hook (--autopush)
  8. write an install manifest (<state home>/install-manifest.json) so --check-drift
     can tell "locally customized" apart from "update available" later

Never sets an API key. Re-runnable (idempotent). See uninstall.py to reverse.

Usage:
  python3 install/install.py                 # interactive, sensible defaults
  python3 install/install.py --yes           # non-interactive
  python3 install/install.py --config config.json
  python3 install/install.py --vault-path ~/notes --lang de --no-examples
  python3 install/install.py --link          # symlink scripts/hooks instead of copy (dev)
  python3 install/install.py --schedule      # also register the nightly graph rebuild
  python3 install/install.py --schedule-dream  # also register the nightly dreaming pass (04:45)
  python3 install/install.py --autopush      # opt-in: commit+push the vault on session end
  python3 install/install.py --check-drift   # compare installed files vs manifest vs repo
"""
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME = os.path.expanduser("~")

# Sentinels that identify OUR hook groups, so re-runs replace rather than duplicate.
HOOK_SENTINELS = (
    "recall-lessons.py", "risk-recall.py", "save_nudge.sh", "health-sentinel.py",
    "vault_autopush.sh", "dream_run.sh", "guard.py", "session-brief.py",
    "checkpoint session log", "graphify: knowledge graph at graphify-out",
)
HOOK_FILES = ("recall-lessons.py", "risk-recall.py", "health-sentinel.py",
              "guard.py", "session-brief.py")
ENGINE_FILES = ("os_lessons.py", "os_doctor.py", "guards.example.json", "README.md")
CLAUDE_MD_START = "<!-- personal-os:start -->"
CLAUDE_MD_END = "<!-- personal-os:end -->"


def expand(p):
    return os.path.abspath(os.path.expanduser(os.path.expandvars(p))) if p else p


def c(s, code):
    return f"\033[{code}m{s}\033[0m" if sys.stdout.isatty() else s


def info(s): print(c("•", "36"), s)
def ok(s):   print(c("✓", "32"), s)
def warn(s): print(c("!", "33"), s)


def default_log_dir():
    base = os.environ.get("XDG_STATE_HOME") or os.path.join(HOME, ".local", "state")
    return os.path.join(base, "personal-os", "logs")


def load_config(args):
    cfg = {
        "vault_dir": "~/vault",
        "claude_dir": "~/.claude",
        "scripts_dir": "~/.personal-os/scripts",
        "log_dir": "",
        "personal_os_home": "",
        "ollama_endpoint": "http://localhost:11434",
        "embed_model": "nomic-embed-text",
        "lang": "en",
        "install_examples": True,
        "schedule_nightly_graph": False,
        "schedule_nightly_dream": False,
        "autopush_on_stop": False,
        "dream_gen_model": "llama3.2:3b",
        "import_chats_nightly": False,
        "auto_install_deps": False,
        "git_author_email": "",
    }
    if args.config:
        with open(expand(args.config)) as f:
            user = json.load(f)
        cfg.update({k: v for k, v in user.items() if not k.startswith("_")})
    if args.vault_path:
        cfg["vault_dir"] = args.vault_path
    if args.lang:
        cfg["lang"] = args.lang
    if args.no_examples:
        cfg["install_examples"] = False
    if args.schedule:
        cfg["schedule_nightly_graph"] = True
    if args.schedule_dream:
        cfg["schedule_nightly_dream"] = True
    if args.autopush:
        cfg["autopush_on_stop"] = True
    if getattr(args, "git_author_email", None) is not None:
        cfg["git_author_email"] = args.git_author_email

    cfg["vault_dir"] = expand(cfg["vault_dir"])
    cfg["claude_dir"] = expand(cfg["claude_dir"])
    cfg["scripts_dir"] = expand(cfg["scripts_dir"])
    cfg["log_dir"] = expand(cfg["log_dir"]) if cfg["log_dir"] else default_log_dir()
    cfg["personal_os_home"] = expand(cfg["personal_os_home"]) if cfg["personal_os_home"] \
        else os.path.join(cfg["claude_dir"], "personal-os")
    cfg["lang"] = (cfg["lang"] or "en").lower()[:2]
    return cfg


def detect_tools():
    return {t: shutil.which(t) for t in ("qmd", "graphify", "ollama", "python3", "jq")}


def confirm(prompt, assume_yes):
    if assume_yes:
        return True
    try:
        return input(prompt + " [y/N] ").strip().lower() in ("y", "yes", "j", "ja")
    except EOFError:
        return False


# ---------------------------------------------------------------- token render

def render_tokens(text, cfg):
    vault = cfg["vault_dir"]
    # permission paths use the //<abs-without-leading-slash> form
    text = text.replace("//${PERSONAL_OS_VAULT}", "//" + vault.lstrip("/"))
    tokens = {
        "PERSONAL_OS_VAULT": vault,
        "PERSONAL_OS_CLAUDE_DIR": cfg["claude_dir"],
        "PERSONAL_OS_SCRIPTS_DIR": cfg["scripts_dir"],
        "PERSONAL_OS_LOG_DIR": cfg["log_dir"],
        "PERSONAL_OS_HOME": cfg["personal_os_home"],
        "PERSONAL_OS_OLLAMA": cfg["ollama_endpoint"],
        "PERSONAL_OS_DREAM_MODEL": cfg["dream_gen_model"],
        "PERSONAL_OS_LANG": cfg["lang"],
    }
    for k, v in tokens.items():
        text = text.replace("${%s}" % k, v)
    return text


# ----------------------------------------------------------------- vault setup

def setup_vault(cfg, dry):
    vault = cfg["vault_dir"]
    scaffold = os.path.join(REPO, "vault-scaffold")
    info(f"vault → {vault}")
    if dry:
        return
    for root, dirs, files in os.walk(scaffold):
        rel = os.path.relpath(root, scaffold)
        target_root = vault if rel == "." else os.path.join(vault, rel)
        os.makedirs(target_root, exist_ok=True)
        for fn in files:
            if fn == ".gitkeep":
                continue
            src = os.path.join(root, fn)
            dst_name = "HOME.md" if fn == "HOME.example.md" else fn
            dst = os.path.join(target_root, dst_name)
            if os.path.exists(dst):
                continue  # never overwrite the user's own notes/config
            shutil.copy2(src, dst)
    if cfg["install_examples"]:
        ex = os.path.join(REPO, "examples")
        n = 0
        for root, _dirs, files in os.walk(ex):
            rel = os.path.relpath(root, ex)
            tr = os.path.join(vault, rel)
            os.makedirs(tr, exist_ok=True)
            for fn in files:
                dst = os.path.join(tr, fn)
                if not os.path.exists(dst):
                    shutil.copy2(os.path.join(root, fn), dst)
                    n += 1
        ok(f"seeded {n} example notes")


# ------------------------------------------------------------- .claude assets

def _place(src, dst, link, backup_dir):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.lexists(dst):
        os.makedirs(backup_dir, exist_ok=True)
        shutil.move(dst, os.path.join(backup_dir, os.path.basename(dst)))
    if link:
        os.symlink(src, dst)
    else:
        shutil.copy2(src, dst)


def setup_claude_assets(cfg, link, dry, backup_dir):
    cd = cfg["claude_dir"]
    info(f"commands/hooks/engine → {cd}")
    if dry:
        return
    # commands (back up any same-named existing command)
    for fn in sorted(os.listdir(os.path.join(REPO, "claude", "commands"))):
        if not fn.endswith(".md"):
            continue
        _place(os.path.join(REPO, "claude", "commands", fn),
               os.path.join(cd, "commands", fn), link, os.path.join(backup_dir, "commands"))
    # hooks
    for fn in HOOK_FILES:
        d = os.path.join(cd, "hooks", fn)
        _place(os.path.join(REPO, "claude", "hooks", fn), d, link, os.path.join(backup_dir, "hooks"))
        os.chmod(d, 0o755)
    # engine
    for fn in ENGINE_FILES:
        _place(os.path.join(REPO, "claude", "personal-os", fn),
               os.path.join(cfg["personal_os_home"], fn), link,
               os.path.join(backup_dir, "personal-os"))
    # qmd skill — only if absent (never clobber an existing skill)
    qmd_skill = os.path.join(cd, "skills", "qmd")
    if not os.path.exists(qmd_skill):
        os.makedirs(qmd_skill, exist_ok=True)
        shutil.copy2(os.path.join(REPO, "claude", "skills", "qmd", "SKILL.md"),
                     os.path.join(qmd_skill, "SKILL.md"))
    else:
        warn("~/.claude/skills/qmd exists — left untouched")
    ok("assets installed")


def setup_scripts(cfg, link, dry):
    sd = cfg["scripts_dir"]
    info(f"scripts → {sd}")
    if dry:
        return
    os.makedirs(sd, exist_ok=True)
    for fn in sorted(os.listdir(os.path.join(REPO, "scripts"))):
        src = os.path.join(REPO, "scripts", fn)
        if not os.path.isfile(src):
            continue  # skip __pycache__ and other dirs
        dst = os.path.join(sd, fn)
        if os.path.lexists(dst):
            os.remove(dst)
        if link:
            os.symlink(src, dst)
        else:
            shutil.copy2(src, dst)
        if fn.endswith((".sh", ".py")):
            os.chmod(dst, 0o755)
    ok("scripts installed")


# --------------------------------------------------------------- settings.json

def deep_merge_settings(cfg, dry, backup_dir):
    cd = cfg["claude_dir"]
    settings_path = os.path.join(cd, "settings.json")
    frag = json.loads(render_tokens(
        open(os.path.join(REPO, "claude", "settings.fragment.json")).read(), cfg))
    info(f"merge hooks/env/permissions → {settings_path}")
    if dry:
        return
    existing = {}
    if os.path.exists(settings_path):
        try:
            existing = json.load(open(settings_path))
        except Exception:
            warn("existing settings.json is not valid JSON — backing up, starting fresh")
        os.makedirs(backup_dir, exist_ok=True)
        shutil.copy2(settings_path, os.path.join(backup_dir, "settings.json"))

    # env: our namespaced keys (safe to set/overwrite)
    env = existing.setdefault("env", {})
    env.update(frag.get("env", {}))

    # permissions.allow: set-union
    perms = existing.setdefault("permissions", {})
    allow = perms.setdefault("allow", [])
    for entry in frag.get("permissions", {}).get("allow", []):
        if entry not in allow:
            allow.append(entry)

    # hooks: drop our previous groups (by sentinel), then append fresh -> idempotent
    hooks = existing.setdefault("hooks", {})
    for event, groups in frag.get("hooks", {}).items():
        cur = hooks.setdefault(event, [])
        cur[:] = [g for g in cur if not _is_ours(g)]
        cur.extend(groups)

    # Vault autopush is OPT-IN, so it is appended programmatically here rather than
    # shipped in the unconditionally-merged settings.fragment.json. The sentinel
    # ("vault_autopush.sh") makes re-runs idempotent either way: a previous autopush
    # group was already dropped above, and it is only re-added if still opted in.
    if cfg.get("autopush_on_stop"):
        stop = hooks.setdefault("Stop", [])
        # any stale autopush group not covered by the fragment purge (e.g. Stop absent
        # from the fragment in a future version) is dropped defensively
        stop[:] = [g for g in stop if "vault_autopush.sh" not in json.dumps(g)]
        stop.append({
            "hooks": [{
                "type": "command",
                "command": '/bin/sh "{}/vault_autopush.sh" 2>/dev/null || true'.format(
                    cfg["scripts_dir"]),
                "timeout": 30,
            }]
        })

    os.makedirs(cd, exist_ok=True)
    json.dump(existing, open(settings_path, "w"), indent=2, ensure_ascii=False)
    ok("settings.json merged (previous backed up)"
       + (" + autopush Stop hook" if cfg.get("autopush_on_stop") else ""))


def _is_ours(group):
    blob = json.dumps(group)
    return any(s in blob for s in HOOK_SENTINELS)


# ------------------------------------------------------------------- guards

def materialize_guards(cfg, dry):
    """guards.example.json -> <personal_os_home>/guards.json (once). The example ships
    an EMPTY author_email placeholder; the materialized file gets your
    git_author_email so the deploy-wrong-author rule can actually fire (empty keeps
    that one rule dormant). NEVER overwrites an existing guards.json — that file is
    user-customized (your own compiled rules live there)."""
    dst = os.path.join(cfg["personal_os_home"], "guards.json")
    info(f"guards → {dst}")
    if dry:
        return
    if os.path.exists(dst):
        warn("guards.json exists — left untouched (your rules; fresh defaults are in "
             "guards.example.json next to it)")
        return
    with open(os.path.join(REPO, "claude", "personal-os", "guards.example.json"),
              encoding="utf-8") as f:
        guards = json.load(f)
    email = (cfg.get("git_author_email") or "").strip()
    for rule in guards.get("rules", []):
        if "author_email" in rule:
            rule["author_email"] = email
    os.makedirs(cfg["personal_os_home"], exist_ok=True)
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(guards, f, indent=2, ensure_ascii=False)
    ok("guards.json materialized (mode: ask-only — shadow week first)"
       + (f" · author guard: {email}" if email
          else " · author guard dormant (no git_author_email)"))


# ----------------------------------------------------------------- CLAUDE.md

def append_claude_md(cfg, dry):
    path = os.path.join(cfg["claude_dir"], "CLAUDE.md")
    snippet = open(os.path.join(REPO, "claude", "personal-os.claude.md")).read().strip()
    block = f"{CLAUDE_MD_START}\n{snippet}\n{CLAUDE_MD_END}\n"
    info(f"Personal OS section → {path}")
    if dry:
        return
    text = open(path).read() if os.path.exists(path) else ""
    if CLAUDE_MD_START in text and CLAUDE_MD_END in text:
        pre = text.split(CLAUDE_MD_START)[0]
        post = text.split(CLAUDE_MD_END, 1)[1]
        text = pre.rstrip() + "\n\n" + block + post.lstrip()
    else:
        text = (text.rstrip() + "\n\n" + block) if text.strip() else block
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").write(text)
    ok("CLAUDE.md updated")


# --------------------------------------------------------------------- qmd

def setup_qmd(cfg, tools, dry, no_embed):
    qmd_cfg_dir = expand(os.path.join(
        os.environ.get("XDG_CONFIG_HOME", os.path.join(HOME, ".config")), "qmd"))
    idx = os.path.join(qmd_cfg_dir, "index.yml")
    tmpl = open(os.path.join(REPO, "config", "qmd-index.example.yml")).read()
    content = tmpl.replace("${VAULT}", cfg["vault_dir"])
    info(f"qmd index config → {idx}")
    if dry:
        return
    os.makedirs(qmd_cfg_dir, exist_ok=True)
    if os.path.exists(idx):
        shutil.copy2(idx, idx + ".bak")
        warn(f"existing index.yml backed up to {idx}.bak")
    open(idx, "w").write(content)
    if not tools["qmd"]:
        warn("qmd not installed — install it (see docs/SETUP.md), then run:  qmd update && qmd embed")
        return
    if no_embed:
        info("skipping index build (--no-embed). Run later:  qmd update && qmd embed")
        return
    # Correct order: `qmd update` indexes the collection files, THEN `qmd embed`
    # generates the vectors vsearch needs. embed alone leaves an empty index.
    info("indexing your vault (qmd update)…")
    try:
        subprocess.run([tools["qmd"], "update"], timeout=1800)
    except Exception as e:
        warn(f"`qmd update` did not complete ({e}); run `qmd update && qmd embed` yourself later")
        return
    info("building the semantic index (qmd embed) — first run downloads local models "
         "(~hundreds of MB, one-time); this can take a few minutes…")
    try:
        subprocess.run([tools["qmd"], "embed"], timeout=3600)
        ok("qmd index built")
    except Exception as e:
        warn(f"`qmd embed` did not complete ({e}); run `qmd embed` yourself later")


# ---------------------------------------------------------------- scheduler

def _base_job_env(cfg):
    return {
        "PERSONAL_OS_VAULT": cfg["vault_dir"],
        "PERSONAL_OS_SCRIPTS_DIR": cfg["scripts_dir"],
        "PERSONAL_OS_LOG_DIR": cfg["log_dir"],
        "PERSONAL_OS_HOME": cfg["personal_os_home"],
    }


def _schedule_job(label, script, hour, minute, env, background=False):
    """Register one nightly job: launchd plist on macOS, crontab hint on Linux."""
    system = platform.system()
    if system == "Darwin":
        plist = os.path.join(HOME, "Library", "LaunchAgents", label + ".plist")
        os.makedirs(os.path.dirname(plist), exist_ok=True)
        env_xml = "\n".join(f"    <key>{k}</key><string>{v}</string>" for k, v in env.items())
        extra = ""
        if background:
            # Low-priority QoS: this job may run a local LLM — it must never compete
            # with foreground work if the machine happens to be awake.
            extra = ("  <key>ProcessType</key><string>Background</string>\n"
                     "  <key>Nice</key><integer>10</integer>\n"
                     "  <key>LowPriorityIO</key><true/>\n")
        open(plist, "w").write(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>{label}</string>
  <key>ProgramArguments</key><array><string>/bin/sh</string><string>{script}</string></array>
  <key>EnvironmentVariables</key><dict>
{env_xml}
  </dict>
{extra}  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>{hour}</integer><key>Minute</key><integer>{minute}</integer></dict>
</dict></plist>
""")
        subprocess.run(["launchctl", "unload", plist], capture_output=True)
        subprocess.run(["launchctl", "load", plist], capture_output=True)
        ok(f"launchd job loaded ({label}, {hour:02d}:{minute:02d})")
    else:
        env_str = " ".join(f"{k}={v}" for k, v in env.items())
        line = f"{minute} {hour} * * * {env_str} /bin/sh {script}"
        warn("Linux: add this to your crontab (`crontab -e`) or a systemd user timer:")
        print("   " + line)


def setup_scheduler(cfg, tools, dry):
    if cfg["schedule_nightly_graph"]:
        if not tools["graphify"]:
            warn("graphify not installed — skipping nightly graph schedule")
        else:
            info(f"nightly graph rebuild ({platform.system()})")
            if not dry:
                env = _base_job_env(cfg)
                env["PERSONAL_OS_IMPORT_CHATS"] = "1" if cfg["import_chats_nightly"] else "0"
                _schedule_job("com.personal-os.graph-rebuild",
                              os.path.join(cfg["scripts_dir"], "graph_rebuild.sh"),
                              4, 15, env)
    if cfg["schedule_nightly_dream"]:
        if not tools["ollama"]:
            # Dreaming degrades gracefully: the LLM-free passes (fires, connections)
            # still run without ollama, so schedule anyway and just say so.
            warn("ollama not installed — dreaming will run its LLM-free passes only "
                 "(install ollama + pull the models to enable the full run)")
        info(f"nightly dreaming pass ({platform.system()})")
        if not dry:
            env = _base_job_env(cfg)
            env["PERSONAL_OS_OLLAMA"] = cfg["ollama_endpoint"]
            env["PERSONAL_OS_DREAM_MODEL"] = cfg["dream_gen_model"]
            env["PERSONAL_OS_EMBED_MODEL"] = cfg["embed_model"]
            _schedule_job("com.personal-os.dream",
                          os.path.join(cfg["scripts_dir"], "dream_run.sh"),
                          4, 45, env, background=True)


# ------------------------------------------------------- manifest & drift check

def _sha256(path):
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _installed_files(cfg):
    """Yield (repo_relpath, installed_dest) for every command/hook/engine/script file."""
    for fn in sorted(os.listdir(os.path.join(REPO, "claude", "commands"))):
        if fn.endswith(".md"):
            yield ("claude/commands/" + fn, os.path.join(cfg["claude_dir"], "commands", fn))
    for fn in HOOK_FILES:
        yield ("claude/hooks/" + fn, os.path.join(cfg["claude_dir"], "hooks", fn))
    for fn in ENGINE_FILES:
        yield ("claude/personal-os/" + fn, os.path.join(cfg["personal_os_home"], fn))
    for fn in sorted(os.listdir(os.path.join(REPO, "scripts"))):
        if os.path.isfile(os.path.join(REPO, "scripts", fn)):
            yield ("scripts/" + fn, os.path.join(cfg["scripts_dir"], fn))


def write_manifest(cfg, dry):
    """Record the sha256 of every file as installed, so --check-drift can later
    distinguish 'you customized this locally' from 'the repo moved ahead'."""
    mpath = os.path.join(cfg["personal_os_home"], "install-manifest.json")
    info(f"install manifest → {mpath}")
    if dry:
        return
    files = {}
    for rel, dest in _installed_files(cfg):
        h = _sha256(dest)
        if h is not None:
            files[rel] = {"sha256": h, "dest": dest}
    os.makedirs(cfg["personal_os_home"], exist_ok=True)
    tmp = mpath + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"version": 1, "ts": datetime.now().isoformat(timespec="seconds"),
                   "files": files}, f, indent=1)
    os.replace(tmp, mpath)
    ok(f"manifest written ({len(files)} files)")


def check_drift(cfg):
    """Three-way compare per installed file: live (installed) vs manifest vs repo.

      live==manifest && repo==manifest  → in sync
      live==manifest && repo!=manifest  → update available (safe to re-run install)
      live!=manifest && repo==manifest  → locally customized (re-install would clobber)
      live!=manifest && repo!=manifest  → conflict (both moved — merge by hand)
    """
    mpath = os.path.join(cfg["personal_os_home"], "install-manifest.json")
    try:
        manifest = json.load(open(mpath))
    except Exception:
        print(f"no readable manifest at {mpath} — run install.py once to create it.")
        return 1
    buckets = {"in sync": [], "update available": [], "locally customized": [],
               "conflict": [], "missing live file": []}
    for rel, entry in sorted(manifest.get("files", {}).items()):
        h_m = entry.get("sha256")
        h_live = _sha256(entry.get("dest", ""))
        h_repo = _sha256(os.path.join(REPO, rel))
        if h_live is None:
            buckets["missing live file"].append(rel)
        elif h_live == h_m and h_repo == h_m:
            buckets["in sync"].append(rel)
        elif h_live == h_m:
            buckets["update available"].append(rel)
        elif h_repo == h_m:
            buckets["locally customized"].append(rel)
        else:
            buckets["conflict"].append(rel)
    print(f"Personal OS — drift check (manifest: {manifest.get('ts', '?')})")
    for name in ("in sync", "update available", "locally customized", "conflict",
                 "missing live file"):
        files = buckets[name]
        if not files:
            continue
        print(f"  {name}: {len(files)}")
        if name != "in sync":
            for rel in files:
                print(f"    - {rel}")
    if buckets["update available"]:
        print("→ re-run install.py to pick up repo updates.")
    if buckets["locally customized"]:
        print("→ locally customized files would be OVERWRITTEN by a re-install "
              "(a backup is taken) — port your changes upstream or keep a copy.")
    if buckets["conflict"]:
        print("→ conflicts need a manual merge before re-installing.")
    return 0


# --------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    ap.add_argument("--vault-path")
    ap.add_argument("--lang", choices=["en", "de"])
    ap.add_argument("--no-examples", action="store_true")
    ap.add_argument("--link", action="store_true", help="symlink instead of copy (dev)")
    ap.add_argument("--schedule", action="store_true",
                    help="register the nightly graph rebuild (04:15)")
    ap.add_argument("--schedule-dream", action="store_true",
                    help="register the nightly dreaming pass (04:45, ~30min after the graph rebuild)")
    ap.add_argument("--autopush", action="store_true",
                    help="opt-in Stop hook: commit+push the vault at session end "
                         "(requires a vault git remote)")
    ap.add_argument("--git-author-email", default=None,
                    help="expected git author email for the deploy-wrong-author guard "
                         "(written into the materialized guards.json; empty keeps "
                         "that rule dormant)")
    ap.add_argument("--no-embed", action="store_true",
                    help="don't build the qmd index now (do it later with qmd update && qmd embed)")
    ap.add_argument("--check-drift", action="store_true",
                    help="compare installed files vs install manifest vs repo, then exit")
    ap.add_argument("--yes", "-y", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cfg = load_config(args)
    if args.check_drift:
        return check_drift(cfg)
    tools = detect_tools()

    if not cfg["git_author_email"] and not args.yes:
        try:
            if sys.stdin.isatty():
                cfg["git_author_email"] = input(
                    "Git author email for the deploy-wrong-author guard "
                    "(Enter = leave that rule dormant): ").strip()
        except EOFError:
            pass

    print(c("\nPersonal OS — install plan", "1"))
    print("  OS:        ", platform.system(), platform.release())
    print("  vault:     ", cfg["vault_dir"])
    print("  ~/.claude: ", cfg["claude_dir"])
    print("  scripts:   ", cfg["scripts_dir"])
    print("  log dir:   ", cfg["log_dir"])
    print("  language:  ", cfg["lang"])
    print("  examples:  ", "yes" if cfg["install_examples"] else "no")
    print("  schedule:  ", ("graph " if cfg["schedule_nightly_graph"] else "")
          + ("dream" if cfg["schedule_nightly_dream"] else "") or "none")
    print("  autopush:  ", "on Stop (opt-in)" if cfg["autopush_on_stop"] else "no")
    print("  guards:    ", "author rule armed ({})".format(cfg["git_author_email"])
          if cfg["git_author_email"] else "ask-only, author rule dormant")
    print("  qmd:       ", c("found", "32") if tools["qmd"] else c("MISSING (core)", "31"))
    print("  graphify:  ", c("found", "32") if tools["graphify"] else c("missing (optional)", "33"))
    print("  ollama:    ", c("found", "32") if tools["ollama"] else c("missing (optional)", "33"))
    print("  jq:        ", c("found", "32") if tools["jq"] else c("missing (Stop-hook nudge)", "33"))
    print()

    if not tools["qmd"]:
        warn("qmd is the core dependency. Install: npm install -g @tobilu/qmd  (see docs/SETUP.md)")
    if args.dry_run:
        info("dry run — no changes will be made")
    elif not confirm("Proceed with the install?", args.yes):
        print("aborted."); return 1

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = os.path.join(cfg["claude_dir"], "backups", "personal-os-" + ts)

    setup_vault(cfg, args.dry_run)
    setup_claude_assets(cfg, args.link, args.dry_run, backup_dir)
    setup_scripts(cfg, args.link, args.dry_run)
    deep_merge_settings(cfg, args.dry_run, backup_dir)
    materialize_guards(cfg, args.dry_run)
    append_claude_md(cfg, args.dry_run)
    setup_qmd(cfg, tools, args.dry_run, args.no_embed)
    setup_scheduler(cfg, tools, args.dry_run)
    write_manifest(cfg, args.dry_run)

    print()
    ok("Personal OS installed.")
    print("  Next: open Claude Code in any project and try  /lesson  ·  /save  ·  /os")
    print("  Verify wiring:  python3 install/doctor.py")
    if not args.dry_run and os.path.isdir(backup_dir):
        info(f"backups of anything replaced: {backup_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
