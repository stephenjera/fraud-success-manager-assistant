-- 001-roles.sql — the two service roles (ADR-0007).
-- Runs as the entrypoint superuser on a fresh volume, or via `psql -f` to repair
-- an existing one. Idempotent: re-running only re-sets the dev password.
-- These are *infrastructure*, not migrating tables — that is the whole point of
-- pulling them out of Alembic (ADR-0015). A downgrade can no longer drop/rename
-- them, because they no longer live in a revision.
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'reference_readonly') THEN
    CREATE ROLE reference_readonly LOGIN PASSWORD 'reference_readonly';
  ELSE
    ALTER ROLE reference_readonly WITH LOGIN PASSWORD 'reference_readonly';
  END IF;

  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_rw') THEN
    CREATE ROLE app_rw LOGIN PASSWORD 'app_rw';
  ELSE
    ALTER ROLE app_rw WITH LOGIN PASSWORD 'app_rw';
  END IF;
END $$;
