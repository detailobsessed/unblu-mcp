---
trigger: always_on
description: Use Graphite CLI to manage our code in this project
---

gt -h
Graphite (gt) simplifies the entire code authoring & reviewing lifecycle
for GitHub. It enables stacking PRs on top of each other to keep you
unblocked & your changes small, focused, and reviewable.

USAGE
  $ gt <command> [flags]

AUTHENTICATING
  Authenticating gt with Graphite enables submitting PRs and stacks:

  1. Open https://app.graphite.dev/settings/cli
  2. Create a new auth token
  3. Paste the generated gt auth --token <token> command into the terminal

TERMS
  stack:     A sequence of pull requests, each building off of its parent.
             ex: main <- PR "add API" <- PR "update frontend" <- PR "docs"
  trunk:     The branch that stacks are merged into.
		         ex: main
  downstack: The PRs below the given PR in a stack, i.e. its ancestors.
  upstack:   The PRs above the given PR in a stack, i.e. its descendants.

CORE COMMANDS
  gt init:            Initializes your Git repo to work with Graphite
  gt create:          Creates a new branch and commit your changes
  gt submit:          Submits the current branch & all downstack
                      branches to Graphite
  gt submit --stack:  Submits your current stack to Graphite
  gt modify:          Amends your current branch with new changes and
                      rebases all PRs above it
  gt restack:         Rebases every PR in a stack to have the latest
                      changes
  gt sync:            Pulls the latest trunk branch, rebases all open
                      PRs/stacks on top of the latest changes, and
                      prompts to delete any stale/old/merged branches
  gt checkout:        Interactively checks out any of your branches
  gt log:             Prints a graphical representation of your current
                      stack
  gt up:              Checks out the branch directly upstack
  gt down:            Checks out the branch directly downstack
  gt demo:            Walks you through examples to learn the Graphite
                      workflow via an interactive tutorial

  Run gt --help --all for a full command reference.
  Pass the --help flag to any command for specific help
  (ex: gt submit --help)

CORE WORKFLOW
  Run gt guide workflow to quickly learn how to:
    - create a new PR
    - stack a PR on top of an existing PR
    - respond to peer feedback from anywhere in your stack
    - sync the latest changes from main
    - merge your stack to your main branch

LEARN MORE
  Learn about custom aliases with gt aliases --help.
  Learn to customize gt with gt config --help.

  More documentation: https://graphite.dev/docs
  Our cheatsheet:     https://graphite.dev/docs/cheatsheet
  Tutorial videos:    https://www.youtube.com/@withgraphite
  Troubleshooting:    https://graphite.dev/docs/troubleshooting

FEEDBACK
	We'd love to hear your feedback! Join our Slack community at:
		https://community.graphite.dev
	or email us at: cli@graphite.dev.
	You can also submit feedback directly via gt feedback, which
	has the ability to attach logs if you're experiencing issues.
