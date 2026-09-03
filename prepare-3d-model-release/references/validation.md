# Validation

Run each helper through `uv`, so it uses the script's declared runtime rather than a globally installed Python:

```sh
uv run scripts/build_release.py --note /absolute/path/to/project.md --dry-run
uv run ../publish-3d-model-release/scripts/create_publish_plan.py --manifest /absolute/path/to/release-manifest.json --dry-run
uv run python -m unittest discover -s tests
```

For a one-off validation of either skill, use `uvx` to provide PyYAML without installing it globally:

```sh
uvx --from pyyaml python /Users/scottgibb/.codex/skills/.system/skill-creator/scripts/quick_validate.py /absolute/path/to/skill
```
