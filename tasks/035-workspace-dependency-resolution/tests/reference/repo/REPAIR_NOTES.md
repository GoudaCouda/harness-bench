# Repair notes

The resolver now evaluates the complete dependency and peer graph before it
chooses a version. Required peers participate in reachability and constraints;
an optional peer does not force installation but is still checked if another
package brings it into the graph. OS and CPU platform markers support both
positive allowlists and explicit negative entries. Unresolvable optional roots
are skipped without weakening required dependencies.

Among valid graphs, the objective first retains resolvable optional roots and
then maximizes current-lock preservation, avoiding gratuitous lock churn. A
semantic-version vector gives deterministic final ties. Verification used
`PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v` and all tests
passed successfully. Integration risk: this bounded resolver intentionally
supports only exact and caret ranges, so production metadata using prereleases
or other range operators must be rejected or handled by the real package manager.
No registry publication or lock deployment was performed.
