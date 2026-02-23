# Contributing

Contributions are welcome! Every little bit helps, and credit will always be given.

## Environment setup

Fork and clone the repository, then:

```bash
cd unblu-mcp
uv sync
```

This installs all dependencies including dev tools. If `uv` is not installed, see the [uv installation guide](https://docs.astral.sh/uv/getting-started/installation/).

Run the CLI with `uv run unblu-mcp [ARGS...]`.

## Tasks

This project uses [poethepoet](https://github.com/nat-n/poethepoet) as a task runner. Run `poe` to list all available tasks. Key tasks:

- `poe check` — lint + type check (parallel)
- `poe fix` — auto-fix lint issues and format
- `poe test` — run tests (excluding slow)
- `poe docs` — serve documentation locally

## Development

1. Create a branch: `git switch -c feature-or-bugfix-name`
2. Make your changes
3. Commit — git hooks automatically run formatting, linting, and tests

Don't worry about the changelog — it is generated automatically from commit messages.

## Commit messages

This project uses [Conventional Commits](https://www.conventionalcommits.org/). A git hook enforces the format, so you'll get immediate feedback if the message doesn't match:

```text
<type>[(scope)]: Subject


[Body]
```

**Subject and body must be valid Markdown.** Subject must have proper casing (uppercase for first letter if it makes sense), but no dot at the end, and no punctuation in general.

Scope and body are optional. Type can be:

- `build`: About packaging, building wheels, etc.
- `chore`: About packaging or repo/files management.
- `ci`: About Continuous Integration.
- `deps`: Dependencies update.
- `docs`: About documentation.
- `feat`: New feature.
- `fix`: Bug fix.
- `perf`: About performance.
- `refactor`: Changes that are not features or bug fixes.
- `style`: A change in code style/format.
- `tests`: About tests.

If you write a body, please add trailers at the end (for example issues and PR references, or co-authors), without relying on GitHub's flavored Markdown:

```text
Body.

Issue #10: https://github.com/namespace/project/issues/10
Related to PR namespace/other-project#15: https://github.com/namespace/other-project/pull/15
```

Common types: `feat`, `fix`, `docs`, `refactor`, `test`, `ci`, `chore`, `perf`.

## Pull requests

Link to any related issue in the PR description. Keep commits focused — one logical change per commit. We squash-merge PRs, so don't worry about a clean commit history within the PR.
