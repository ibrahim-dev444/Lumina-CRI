# Working on Lumina together

Several of us change this code at the same time. These rules keep `main` working for everyone. If something here is unclear, ask in the team chat before guessing.

## 1. Getting access

The repository owner adds each person under **GitHub → Settings → Collaborators → Add people**. Use your own GitHub account; never share one login. Accept the email invite, then follow the setup in [README.md](README.md).

## 2. Never work directly on `main`

`main` must always run. All work happens on a branch and comes back through a pull request (PR).

Branch names:

| Kind of work | Branch name |
|---|---|
| New feature | `feature/short-description`, e.g. `feature/ckyc-connector` |
| Bug fix | `fix/short-description`, e.g. `fix/mobile-cleaning` |
| Docs only | `docs/short-description` |

## 3. The daily loop

Start a new piece of work:

```
git switch main
git pull
git switch -c feature/your-change
```

While you work, save progress often:

```
git add .
git commit -m "feat(ingestion): add CKYC connector"
git push -u origin feature/your-change     # first push; later just: git push
```

When it is ready, open a pull request on GitHub into `main`.

Keep your branch up to date with what others merged (do this at least once a day):

```
git switch main
git pull
git switch feature/your-change
git merge main
```

If Git reports a conflict, open the listed files, keep the right version of each marked block, then `git add` the files and `git commit`. Ask for help if you are not sure which version is right; do not delete someone else's work to make the conflict go away.

## 4. Pull requests

- Keep a PR small: one feature or one fix. Small PRs get reviewed quickly and break less.
- Before opening it, run the checks yourself: `pytest` in `backend/`, then `npm run build` and `npm run lint` in `frontend/`. GitHub runs the same checks automatically on every PR (see `.github/workflows/ci.yml`); a red check must be fixed before merging.
- At least one other person reviews and approves before merging. The author clicks **Merge**.
- In the PR description, say what changed, why, and how to test it. Add a screenshot for UI changes.
- After merging, delete the branch on GitHub.

Reviewers check:
- Does it do what the description says, and do the tests cover it?
- Is personal data (mobile, email, date of birth, PAN) still masked for roles that should not see it?
- Are new actions written to the audit log?
- No passwords, keys or real customer data in the code.

## 5. Commit messages

Use the form `type(area): what changed`, in the present tense:

```
feat(mdm): match on PAN when both records have one
fix(ingestion): accept mobile numbers with a leading 0
docs: explain how to reset local data
test(api): cover masking for the agent role
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`.

## 6. Database changes (migrations)

Each of us has our own Postgres in Docker. We share the **structure** through migration files in git, never by copying databases.

- Changed a model? Run `python manage.py makemigrations`, then commit the new file in `migrations/` **in the same PR** as the model change.
- After every `git pull`, run `python manage.py migrate`.
- Never edit or delete a migration that is already on `main`. Write a new one.
- If two PRs both added a migration to the same app, Django reports "Conflicting migrations". Pull `main`, run `python manage.py makemigrations --merge`, commit the merge file.
- Starting data that everyone needs (like source trust levels or field weights) goes in a data migration, so every database gets it automatically.

## 7. Secrets and personal data

- `.env` is never committed. Each person makes their own from `.env.example`.
- Never paste passwords, secret keys or tokens into code, commits, PRs, screenshots or chat.
- Added a new setting? Add it to `.env.example` with a fake placeholder value, and mention it in your PR.
- Only fake data goes in the repo (`fake_sources/`, `docker/postgres/init/`). Never commit real customer data, even for testing.
- If a secret is committed by mistake, tell the team at once. Deleting it in a later commit is not enough: it stays in the history and must be changed.

## 8. Adding packages

- Python: `pip install some-package`, then add it with its exact version to `backend/requirements.txt` (copy the line from `pip freeze`).
- Frontend: `npm install some-package`, then commit both `package.json` and `package-lock.json`.
- Mention new packages in your PR so others know to run `pip install -r requirements.txt` or `npm install` after pulling.

## 9. Where code goes

The backend is a **modular monolith**: one Django project split into apps with clear borders.

| App | Owns |
|---|---|
| `sources` | The list of bank systems and their trust |
| `ingestion` | Connectors, raw records, cleaned records |
| `mdm` | Matching, golden records, trust scores, match suggestions |
| `accounts` | Roles, permissions, masking |
| `audit` | The audit log |
| `api` | HTTP endpoints only; it calls the other apps' functions |

Rules:
- Each app writes only its own tables.
- Business logic lives in service files (`sync.py`, `services.py`, `matching.py`), not in views or management commands, so it can be tested and reused.
- Dependencies point one way: `sources` ← `ingestion` ← `mdm` ← `api`. An app never imports from an app that depends on it.
- Who may do what is defined in one place, `backend/accounts/roles.py`. Change permissions there, and add a test.

Frontend:
- Pages call the backend only through `frontend/src/api/client.ts`.
- Colours and sizes come from `frontend/src/styles/tokens.css`; do not hard-code hex colours in components.
- Hide buttons a role cannot use with `useCan(...)`, but remember the API is what actually enforces it.

## 10. Line endings

`.gitattributes` makes Git store every text file with Unix line endings, so files do not show as changed just because someone is on Windows and someone else is on a Mac. You do not need to do anything.
