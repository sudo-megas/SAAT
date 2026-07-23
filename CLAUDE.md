# SAAT

See [`SPEC.md`](SPEC.md) — it is the authoritative project specification. Read it
before making changes.

## Release discipline

Every milestone bumps `__version__` in `saat/__init__.py` and adds its entry to
`CHANGELOG.md`, in the same commit. `tests/test_version.py` enforces this: the test
suite fails if `__version__` doesn't match the most recent version heading in
`CHANGELOG.md`.
