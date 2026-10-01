# Native-assistant engineering trial

This records actual native-assistant choices and individual tools, not a script posing as an agent or an API-powered standalone product. The exact runtime model identity is unverified. No external model API, key, or paid inference is used.

`protocol.json` is the pre-heldout contract. `development_task.json` is the disclosed development task. The public trace records tool inputs, outputs and concise decision summaries only. Native orchestration occurs in the assistant conversation; the CLI is a deterministic tool adapter, not an LLM runtime.

The unchanged pressure-fin solver is staged from an audited immutable package into each task session. Each evaluate command executes one declared design/case/mesh. There is no auto-search, coefficient adjustment, task editing, or selection policy in the tool. Each result distinguishes numerical validity, Reynolds applicability and synthetic engineering requirements. Archived failures remain failures.

Use `python -m aerolab.agent_trial --help`. Optional existing NumPy/SciPy and CadQuery are required for live solves and genuine CAD generation. The adapter does not install dependencies.

Requirements and source hashes, tool budgets, all decisions/errors, selected CAD checks, and per-case mesh convergence are preserved with the session. This demonstrates a bounded human-launched native-agent workflow. One independent heldout task cannot establish broad engineering generalization, physical validation, autonomous operation, aircraft design capability, or manufacturing readiness.

Integrity limits: local hashes detect inconsistent edits but are not signatures or proof against complete history rewriting. The independent evaluator must compare the released task and frozen adapter/protocol hashes to its separate commitments. Conversation tool calls provide the external action record. Model identity, absence of external API use, and human-intervention counts are explicit execution declarations, not independently instrumented identity attestations. Wall-clock overruns are retained and fail acceptance; the adapter does not forcibly terminate a running numerical library call at the deadline.

After a session is finalized, audit its saved records without NumPy, SciPy, or CadQuery:

```sh
python -S scripts/verify_native_agent_trial.py --session research/native_agent_trial/runs/development
```

This is evidence verification, not a replayed agent or a fresh numerical solve. Restoring CAD: concatenate each artifact's `chunks` in listed order, verify the gzip SHA-256, then gzip-decompress to `.step` or `.stl`. Filenames, hashes and units are recorded in the CAD result. The native adapter itself can reproduce individual chosen numerical/CAD tool actions in a new session, but prerecorded actions are not a new independent reasoning trial.
