# Migration contract

Both 0007 branches shipped in separate environments. Create one merge head depending on both branches. Data code must use the historical model, fill only null region values, and reverse only values it introduced. Both an empty database replay and an upgrade from 0006 must pass.
