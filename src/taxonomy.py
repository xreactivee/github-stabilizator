from __future__ import annotations

from typing import Any

SAAS_DESCRIPTION_EXAMPLE = "us-stream — self-hosted streaming platform for teams."
PROJECT_DESCRIPTION_EXAMPLE = (
    "A modern, interactive neumorphic loading screen & portfolio intro experience "
    "built with Next.js 16, React 19, Tailwind CSS v4, and Framer Motion."
)

README_SKELETON = """\
# <Project Name>

<one line, same wording as the repo description>

## Features
- ...

## Tech Stack
- ...

## Installation
```bash
git clone https://github.com/<username>/<repo>.git
cd <repo>
<install command>
```

## Usage
<how to run it>

## License
<license name>
"""

CANONICAL_TOPIC_SPELLINGS = """\
typescript (not ts), javascript (not js), nextjs (not next-js/next.js),
react (not reactjs/react-js), tailwind-css (not tailwind/tailwindcss),
self-hosted (not selfhosted), electron (not electronjs), cli (not command-line)
"""


def normalize_topic(topic: str) -> str:
    normalized = topic.strip().lower().replace(" ", "-").replace("_", "-").replace(".", "")
    while "--" in normalized:
        normalized = normalized.replace("--", "-")
    return normalized.strip("-")


def build_prompt(context: dict[str, Any], category_override: str | None = None) -> str:
    readme_excerpt = (context.get("readme") or "")[:6000]
    code_excerpts = context.get("code_excerpts") or "(no source files fetched)"
    override_block = (
        f"\nIMPORTANT OVERRIDE: classify this repo as category=\"{category_override}\" "
        f"regardless of your own judgement, and follow that category's description "
        f"pattern exactly.\n"
        if category_override
        else ""
    )

    return f"""You are standardizing metadata for one repository in a GitHub account so that
every repository follows the exact same conventions. Respond with a SINGLE JSON object only,
no markdown fences, no commentary, matching this schema:

{{
  "category": "saas" | "project" | "other",
  "description": "string, <=350 chars",
  "topics": ["6 to 7 lowercase-hyphenated topic strings"],
  "readme_markdown": "full replacement README.md content, markdown",
  "notes": "short string: anything you deliberately left unchanged and why"
}}

## Classification rule
- "saas": the repo is a hosted product/service with a brand-like name (examples of this
  account's SaaS project names: anyget, lucent). Its description MUST follow the pattern:
  "{SAAS_DESCRIPTION_EXAMPLE}" — i.e. "<project-name> — <short lowercase pitch>.".
- "project" (tool, portfolio piece, experiment, library, etc.): description MUST follow the
  pattern: "{PROJECT_DESCRIPTION_EXAMPLE}" — i.e. "A <adjective(s)> <what it is> built with
  <tech stack, comma separated>.".
- "other": only if neither pattern genuinely fits (rare). Keep description in the same
  spirit: one sentence, no marketing fluff, no emoji.

## Content accuracy rule (applies to description AND every README section)
The "what it is" part of the description, and every bullet under Features, MUST state
what the project actually DOES — derived from the source excerpts below (function/route/
component names, CLI commands, API calls, data it reads or writes) — not just its platform
or tech stack. A generic label like "desktop application", "web app", "script", or "tool"
is NEVER acceptable on its own — always follow it with the concrete behavior, e.g. instead
of "a desktop application built with Electron" write "a desktop app built with Electron
that <does X, using Y>". If the source excerpts genuinely don't reveal enough to say more
than the generic label, say so explicitly in "notes" instead of inventing functionality.
Never guess or fabricate a feature that isn't backed by the README or the source excerpts.

## Topics rule
Produce 6-7 topics. Every topic MUST be genuinely and specifically about THIS
repository's own name, description, language and README content below — never invent
topics that describe some other kind of project. Do not reuse or guess topics from any
other repository; you are only shown this one repo's context, so derive topics from it
alone. Use these canonical spellings when the concept applies, instead of inventing a
synonym: {CANONICAL_TOPIC_SPELLINGS}

## README rule
- Follow this skeleton (adapt sections to what the project actually has, don't invent
  features that don't exist):
{README_SKELETON}
- No emoji, no inflated marketing language, no filler ("This awesome project..."). Sade
  (plain), accurate, and to the point.
- The Installation section's clone command MUST use the REAL clone URL given below —
  never leave placeholders like `<your_username>`, `<your-username>`, `yourusername`,
  or `YOUR_USERNAME`. If the current README contains such a placeholder, replace it with
  the real URL.
- If the current README already contains real, accurate content (features, usage
  details) not present in the raw context below, preserve that information — you are
  restyling, not deleting real project information.

{override_block}
## Repository context
- name: {context['name']}
- real clone url: {context['clone_url']}
- primary language: {context.get('language') or 'unknown'}
- current description: {context.get('description') or '(empty)'}
- current topics: {', '.join(context.get('topics') or []) or '(none)'}
- has LICENSE already: {bool(context.get('license'))}
- current README (may be empty or messy, this is what you are replacing):
---
{readme_excerpt}
---
- source file excerpts (manifest + entry-point files, truncated; this is your primary
  evidence for what the project actually does — read them before writing the description
  and Features section):
---
{code_excerpts}
---
"""
