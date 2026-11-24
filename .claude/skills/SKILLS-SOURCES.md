# Agent skills in this project

| Skill(s) | Origin | Version | License |
|---|---|---|---|
| `getting-started`, `design-agent`, `design-task`, `check-crewai-api`, `test-crewai-project`, `connect-tools-and-mcp`, `ask-docs` | Official CrewAI skills, https://github.com/crewAIInc/skills (`skills/`), referenced by https://docs.crewai.com/en/skills | commit `bebb6e8fc10bb8d07961969fb7bfd7d6091b421a` (2026-11-24) | MIT |
| `langfuse` | Official Langfuse skill, https://github.com/langfuse/skills (`skills/langfuse/`), referenced by https://langfuse.com/docs/api-and-data-platform/features/agent-skill | commit `f0bcb13088b490c04b3f4870bace17f6d57b199c` (2026-11-24) | MIT |
| `rag-evaluation-report` | Created for this project; source in `.agents/skills/rag-evaluation-report/`, symlinked here so Claude Code can invoke it | - | - |
| `speckit-*` | Spec Kit 0.13.0 (`specify init --integration claude`) | 0.13.0 | MIT |

Not installed from the CrewAI pack (out of scope for this project): `deploy-to-amp`,
`call-deployed-crew` (CrewAI AMP cloud deployment), `build-flow` (the project uses a
sequential crew, not a Flow).

Equivalent official install commands:

```sh
npx skills add crewaiinc/skills
npx skills add langfuse/skills --skill "langfuse"
```

The skills were installed by copying the folders from the commits above, so the installed
content is pinned and reviewable.
