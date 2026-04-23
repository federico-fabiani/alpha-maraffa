---
applyTo: "game/backend/**"
---
Use Python with FastAPI. Dependency management: uv (uvx for tools)

# 0. Core Principle

Keep code **explicit and greppable**. Avoid magic, metaprogramming, and dynamic dispatch unless strictly necessary.

---

# 1. Architecture (NON-NEGOTIABLE)

Follow strict layering:

- **Domain** → pure logic, no framework or infra dependencies
- **Infrastructure** → DB, APIs, external systems
- **Application** → orchestration (FastAPI, entrypoints)

Dependencies must flow **inward only**:

```
Application → Domain ← Infrastructure
```

Violations are not allowed.

---

# 2. Structure

Organize by **feature**, not by technical layer.

Avoid:

- `utils/`
- `helpers/`

Use `shared/` only if **3+ real usages** exist.

Each module must have a **single, clear responsibility**.

---

# 3. Module Conventions

Use consistent naming:

- `service.py` → orchestration
- `models.py` → data structures
- `schemas.py` → API validation
- `config.py` → configuration
- `exceptions.py` → domain errors
- `base.py` → abstractions (only if justified)

---

# 4. Imports (CRITICAL)

- Use **absolute imports only**
- Do NOT re-export from `__init__.py`
- No executable logic in packages (except root init if explicitly required)

---

# 5. Database Rules

- Prefer ORM/Core expressions over raw SQL
- Use raw SQL only when strictly necessary

Repositories:

- live under a dedicated DB layer
- are instantiated (no staticmethods)
- open a session per usage (no global sessions)

Avoid custom DB abstractions unless clearly needed.

---

# 6. Error Handling

- Raise exceptions inside layers
- Translate errors at boundaries (e.g. FastAPI)

Rules:

- Never fail silently
- Always log unexpected errors
- Do not leak internal details to external interfaces

---

# 7. Light CQS

In orchestration code:

- Queries → `get_*`, `list_*` (no side effects)
- Commands → `create_*`, `execute_*`, `delete_*`

Do not mix responsibilities.

---

# 8. Dependency Management

Use **uv only**:

- Add → `uv add <package>`
- Remove → `uv remove <package>`
- Dev → `uv add --dev <package>`

Never edit `pyproject.toml` manually.

---

# 9. Documentation Model

- Root `README.md` = entry point
- `docs/` = supporting documents
- Package documentation lives in `__init__.py` docstrings only

Keep documentation minimal and aligned with code.

---

# 10. After Changes

- Fix linting and formatting before responding
- Do not leave type errors or lint warnings

---

End of instructions.
