# Repair a split Python namespace package

Work only in `/workspace/repo`. Two independently owned source roots contribute plugins under `acme.plugins`. Production composes both roots, but one root now shadows the other depending on `PYTHONPATH` order.

Inspect package markers, ownership notes, module origins, and `tools/probe_imports.py`. Make the smallest repository change that restores both plugins for either supported path order without copying modules between owners or adding an import shim. Run the offline probe and retain `out/import_probe.json`. Write `IMPORT_HANDOFF.md` with the cause, ownership boundary, exact change, probe matrix, and verification.

Do not edit plugin implementations, ownership records, or the probe. Do not install packages or contact external systems.
