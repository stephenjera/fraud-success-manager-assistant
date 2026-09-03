-- 002-schemas.sql — the two schema objects + the appstate role binding (ADR-0007).
-- Idempotent: safe to re-run via `psql -f` to repair an existing cluster.
--
-- Ownership split (the whole point of this refactor, ADR-0015):
--   * reference  -> the seed owns it (tables + grants + data). Not created-granted here
--                   because the seed creates the tables as the superuser; granting before
--                   they exist is a no-op. The seed grants SELECT to reference_readonly.
--   * appstate   -> app_rw OWNS the schema, so `alembic upgrade head` as app_rw can
--                   CREATE/DROP its tables and `store` as app_rw can DML — without either
--                   role ever being a superuser or touching reference. A wrong `downgrade`
--                   is at worst a DROP TABLE: app_rw cannot drop the schema, the roles, or
--                   reference. That is the boring-rollback property the old rename-downgrade
--                   in 0001 did not have.
CREATE SCHEMA IF NOT EXISTS reference;
CREATE SCHEMA IF NOT EXISTS appstate;

ALTER SCHEMA appstate OWNER TO app_rw;
GRANT USAGE, CREATE ON SCHEMA appstate TO app_rw;
