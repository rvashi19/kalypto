# Attribution

The reviewer agents in `.claude/agents/` and the coding rules in `.claude/rules/`
are adapted from **ECC** (https://github.com/affaan-m/ECC), licensed under the MIT
License, Copyright (c) 2026 Affaan Mustafa.

Only the inert, stack-relevant pieces were adopted (FastAPI/Python/React/TypeScript
review agents and coding rules). ECC's hooks, installer scripts, Node runtime, and
skill packs were intentionally **not** adopted — no third-party code executes as part
of this project from ECC.

MIT License text: https://github.com/affaan-m/ECC/blob/main/LICENSE
