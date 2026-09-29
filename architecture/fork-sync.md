# Automatic fork sync

Every push to `Automo-ASK/Clippit` on `main` starts
`.github/workflows/sync-fork.yml`. The workflow fetches
`qcoderx/Clippit`, merges the pushed upstream commit into the fork's `main`
branch, and pushes the merge back to the fork.

The workflow deliberately merges instead of force-pushing. This keeps any
fork-specific commits and makes the shared history auditable.

## One-time credential setup

Cross-repository pushes cannot use the upstream repository's automatic
`GITHUB_TOKEN`. Add a fine-grained personal access token to the upstream
repository as an Actions secret:

1. Create a fine-grained GitHub token for the account that can write to
   `qcoderx/Clippit`.
2. Give it access only to `qcoderx/Clippit` with **Contents: Read and write**.
3. In `Automo-ASK/Clippit`, open **Settings**, **Secrets and variables**,
   **Actions**, then **New repository secret**.
4. Name the secret `FORK_SYNC_TOKEN` and paste the token as its value.

Do not put the token in this repository, an environment example, a workflow
file, or a chat message. Rotate it immediately if it is ever exposed.

The workflow can be tested at any time with **Actions**, **Sync qcoderx fork**,
**Run workflow**. It exits successfully without creating a commit when the
fork already contains the upstream revision.
