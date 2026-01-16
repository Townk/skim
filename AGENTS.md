# Agents Instructions

<!-- OPENSPEC:START -->
## OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:

- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big
  performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:

- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so `openspec update` can refresh the instructions.
<!-- OPENSPEC:END -->

## Git Commit Instructions

When you need to create a commit, ALWAYS follow the following rules, and NEVER
skip any of these:

- Subject message starts with an emoji from the GitMoji spec (ALWAYS use the
  actual emoji, and not its textual representation);
- Limit the subject line to 50 characters;
- Capitalize the subject line;
- Do not end the subject line with a period;
- Use the imperative mood in the subject line;
- Use Markdown notation to write the commit's body;
- Separate the subject from the body with an H2 heading (`##`) with the title
  "Change Description";
- Always have just one empty line between a heading and any other text;
- Wrap the body at 72 characters;
- Use the body to explain what changes you have made and why you made them;
- Do not assume the reviewer understands what the original problem was, ensure
  you add it;
- Do not think your code is self-explanatory;
- Use '-' for itemized lists, and ensure each item has a ';' at the end of it;
- On list items longer than 72 characters, make sure you wrap the text, and use
  dangling space to indicate a text continuation;
- Always ask the user if you should add an entry in the CHANGELOG file
  regarding this commit. If the user says "yes", add the proper entry before
  committing, and commit the CHANGELOG with the change.
