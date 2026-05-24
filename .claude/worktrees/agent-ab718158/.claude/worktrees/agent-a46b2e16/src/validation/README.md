# Validation Database

This module handles the storage of test data for validating the "LocalAI + Script" hypothesis.

## Setup

### Local Testing (SQLite)
By default, `ValidationDB` uses a local SQLite file (`validation.db`). This allows you to run tests immediately without external dependencies.

```python
from validation.db import ValidationDB
db = ValidationDB()
db.add_call(...)
```

### Production (Supabase)
To migrate to Supabase:
1. Go to the SQL Editor in your Supabase dashboard.
2. Copy the contents of `schema.sql` and run it.
3. Update `db.py` to use `supabase-py` or `SQLAlchemy` with a Postgres connection string.

## Schema
- **calls**: Stores the raw transcripts.
- **expected_outputs**: Stores the "Ground Truth" (what the AI *should* have caught).
- **test_runs**: Stores the actual output from a model run.
- **test_results**: Stores the pass/fail evaluation of a run.
