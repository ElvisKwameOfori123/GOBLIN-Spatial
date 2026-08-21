# Scripts

The supported model runtime is provided by the `goblin_spatial` package and its command-line entry points. Files in `scripts/` are retained only when they serve a clear validation, provenance or first-principles reconstruction role.

Normal users should not assemble scenario results by chaining standalone scripts.

## Historical baseline

Build the validated historical baseline with:

```bash
goblin-spatial build --config configs/ireland_2015_2025.yaml
```

The package modules are the scientific implementation. Older standalone research scripts are useful only as regression/provenance references and should not be treated as a second runtime engine.

## Principal scenarios

Run the supported scenario chain with:

```bash
goblin-spatial-principal <SCENARIO_ID> --baseline-year 2020 --stage SC1
goblin-spatial-principal <SCENARIO_ID> --baseline-year 2020 --stage SC2
goblin-spatial-principal <SCENARIO_ID> --baseline-year 2020 --stage SC3
```

No standalone Styles, generic spared-land screening or sequential-reduction script is part of the supported framework.

## Spatial reconstruction

The remaining spatial scripts may be used explicitly to reproduce compact soil/LPIS controls from version-pinned source data. These are reconstruction workflows, not dependencies of a normal 2020 scenario run.

Heavy reconstruction should therefore be invoked deliberately and validated against the frozen compact-control contracts before any regenerated file is promoted into the runtime data bundle.
