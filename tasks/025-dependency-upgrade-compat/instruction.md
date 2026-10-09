# Prepare the catalog slug dependency upgrade

The catalog ingestion team needs a review-ready maintenance patch before its
next release. The repository is already staged at `$WORKSPACE/repo`.

Security engineering has approved the 8.x line of `python-slugify` and has
retired the repository's current 6.x pin. The wrapper is used to produce stable
catalogue URL keys, including for multilingual feeds, so this cannot be treated
as a version-only edit.

Read the request in `repo/docs/security-upgrade-request.md`, then inspect the
package metadata, the current wrapper, the downstream feed caller, the supplied
fixture, the public tests, and the last CI failure. Prepare the smallest patch
that satisfies the request.

Your final repository must:

- declare only the approved 8.x `python-slugify` runtime dependency;
- leave every other `pyproject.toml` field unchanged;
- keep the public function
  `make_slug(title, preserve_unicode=False, separator="-")` compatible with the
  behavior in the security request;
- use the declared third-party package directly, without a local fallback,
  vendored implementation, network call, or unrelated dependency;
- keep `feed_import.py`, the public tests, fixtures, and evidence documents
  unchanged; and
- pass the local public suite with the 8.x dependency provided by the task
  image.

Modify only:

- `repo/pyproject.toml`
- `repo/src/catalog_slug/slugger.py`

Also create `repo/UPGRADE_NOTES.md`. Write it as a short reviewer handoff with
three clear sections:

1. the dependency and source decision;
2. the exact local verification you actually performed and its result; and
3. compatibility risks plus a rollback/containment plan that keeps the
   dependency on an approved 8.x release. The retired 6.x line is not a safe
   rollback target.

## Auditable wrapper boundary

The review grader treats `slugger.py` as untrusted source data and will not
import or execute it. Keep this security-sensitive adapter small enough for a
static source review:

- import the installed `slugify` function directly at module scope, without an
  alias or compatibility fallback;
- keep `make_slug` as the only function and preserve the exact public signature
  and defaults above;
- make the two published validation decisions directly in the wrapper: reject
  non-string titles, and reject any separator that is not the string `-` or
  `_`, without imposing additional restrictions on valid titles;
- normalize legacy underscore separators before delegation, using either the
  standard string operation or the standard-library regular-expression module;
  and
- delegate once to the dependency, forwarding the Unicode and separator
  options from the caller.

Keep the module side-effect free. Do not add helper indirection, dynamic or
function-local imports, decorators, loops, exception-based fallbacks,
file/process/network access, or other runtime mechanisms to this adapter. These
constraints define a reviewable implementation boundary; they are not a
whitespace, local-variable-name, or exact source template.

The task is offline. From `repo`, the intended public verification command is:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider
```

Do not edit tests to make the change pass, do not install packages over the
network, and do not claim that a deployment or production rollback occurred.
The public pytest suite is the executable check available to you in the task
container; hidden grading conservatively checks the published source invariants
and does not trust a candidate-authored test result.
