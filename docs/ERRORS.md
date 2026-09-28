# Error reference

Generated from `docops/errors.py` by `python scripts/check_error_catalog.py --write`.
Every error printed by Farol carries one of these codes and a next step.

| Code | What happened | What to do |
|---|---|---|
| `already_accepted` | The task was already accepted with other content | `farol task next` |
| `asr_unavailable` | Local speech recognition is not installed | `pip install farol-kit[media]` |
| `backend_closed` | The backend was closed | `reopen the reader` |
| `block_duplicate` | Duplicate block ids in the index input | `farol build` |
| `budget_exceeded` | The answer is longer than its token budget | `shorten it and resubmit` |
| `candidate_unknown` | The index candidate was not prepared | `farol build` |
| `chapter_invalid` | Invalid chapter name | `use a chapter file listed by list_skills` |
| `chapter_links_missing` | SKILL.md does not link every chapter | `link each chapter under ## Chapters` |
| `chapter_too_large` | A chapter covers too much source | `split it into smaller chapters` |
| `chapter_unknown` | Chapter not found | `use a chapter file listed by list_skills` |
| `dependencies_pending` | Earlier tasks must be accepted first | `farol task next` |
| `document_invalid` | An index document is malformed | `farol build` |
| `document_missing` | A corpus document listed in the package is missing | `farol build` |
| `document_unknown` | The document is not indexed | `use a document_id returned by search_knowledge` |
| `documents_invalid` | Index input is malformed | `farol build` |
| `download_failed` | A download failed | `check the network and retry farol build` |
| `duplicate_sections` | A section appears in two chapters | `assign each section once` |
| `embedding_profile_changed` | The index was built with another embedding model | `farol build` |
| `empty_reference_file` | glossary/patterns/cheatsheet has no items | `add list items and resubmit` |
| `extra_required` | An optional extra is not installed | `pip install farol-kit[media]` |
| `extraction_empty` | A document produced no text blocks | `check the file, then farol build` |
| `frontmatter_invalid` | SKILL.md frontmatter is incomplete | `set name and a when-to-use description` |
| `harness_unknown` | Unknown AI agent | `farol connect claude-code` |
| `index_missing` | No factual index yet | `farol build` |
| `index_unknown` | The index revision does not exist | `farol doctor --fix` |
| `index_unreadable` | The index file is damaged | `farol doctor --fix` |
| `install_invalid` | The installed skill failed package validation | `farol doctor --fix` |
| `invalid_query` | The search query is empty | `ask with words describing the fact you need` |
| `library_unknown` | No such project in the library | `farol library list` |
| `mapping_empty` | The source produced no indexable text | `check the source content, then farol build` |
| `media_unreadable` | The audio or video could not be decoded | `convert it to mp3/wav and add it again` |
| `missing_citations` | Factual statements lack block references | `cite blocks like [b12] and resubmit` |
| `missing_file` | An expected answer file is missing | `add the file listed in the task and resubmit` |
| `missing_section` | A required section is missing | `add the section named in the message` |
| `no_sources` | The project has no sources | `farol add <source>` |
| `nothing_to_connect` | No source has been built yet | `farol build` |
| `orphan_sections` | Some sections are not in any chapter | `assign every section to a chapter` |
| `outline_invalid` | The outline is not valid JSON of the expected shape | `fix outline.json and resubmit` |
| `output_invalid` | The answer directory is unsafe or too large | `submit a regular folder with the files` |
| `package_invalid` | Not a Farol package | `run the command inside a project or pass --package` |
| `package_unknown` | No package with that name | `call list_skills to see packages` |
| `plan_missing` | No synthesis plan yet | `farol task plan` |
| `project_missing` | No Farol project here | `farol add <source>` |
| `project_version_unsupported` | farol.json comes from a newer Farol | `pipx upgrade farol-kit` |
| `revision_mismatch` | The query targets another project revision | `reopen the reader` |
| `schedule_unknown` | Unknown scheduler | `farol sync --schedule cron` |
| `skill_unknown` | No skill with that name | `call list_skills` |
| `source_id_taken` | Another source already uses that id | `farol add <source> --name <new-id>` |
| `source_inside_packages` | Sources cannot live inside the project's packages folder | `add a folder outside packages/` |
| `source_not_found` | The source path does not exist | `check the path, then farol add <source>` |
| `task_unknown` | Unknown task id | `farol task status` |
| `transcript_empty` | No speech was recognized | `check the audio or provide a .vtt/.srt file` |
| `transcript_unavailable` | The video has no captions in your languages | `download the audio and farol add the file (local ASR)` |
| `unknown_reference` | A cited block is not part of this task | `cite only blocks listed in the task` |
| `unknown_sections` | The outline uses unknown section ids | `use only the listed section ids` |
| `unsafe_content` | The answer contains instructions aimed at AI agents | `remove them and resubmit` |
| `verbatim_copy` | Too much text is copied from the source | `paraphrase and resubmit` |
| `youtube_blocked` | YouTube asked to sign in | `set FAROL_YTDLP_COOKIES=<cookies.txt> or farol add the downloaded .vtt/audio` |
| `youtube_unavailable` | YouTube metadata could not be read | `check the URL and retry farol build` |
