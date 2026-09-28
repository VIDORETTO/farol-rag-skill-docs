# MCP tools reference

Generated from the code by `python scripts/gen_reference.py`. The `farol` server speaks MCP over
stdio (protocol versions 2025-06-18, 2025-03-26 and 2024-11-05) and is read-only.

## search_knowledge

Search the package's indexed sources for literal facts (defaults, versions, signatures, values, quotes). Every hit carries a citation to cite in the answer. Returns insufficient_evidence when nothing supports the query.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `query` | string | yes | What to look for, in natural words. |
| `top_k` | integer | no |  |
| `package` | string | no | Limit the search to one package (see list_skills). |

## get_document

Return every indexed block of one source document, in order, with locators.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `document_id` | string | yes |  |
| `package` | string | no |  |

## list_skills

List the package's conceptual skills (mental models, decisions, patterns) and their chapters.

No parameters.

## get_skill

Read a skill's SKILL.md, or one of its chapters, for conceptual guidance.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes |  |
| `chapter` | string | no |  |
