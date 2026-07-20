\set ON_ERROR_STOP on

\if :{?migrator_password}
\else
  \echo 'Pass migrator_password as a psql variable'
  \quit 3
\endif
\if :{?runtime_password}
\else
  \echo 'Pass runtime_password as a psql variable'
  \quit 3
\endif

SELECT format('CREATE ROLE fido_migrator LOGIN PASSWORD %L', :'migrator_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fido_migrator')
\gexec
SELECT format('ALTER ROLE fido_migrator LOGIN PASSWORD %L', :'migrator_password')
\gexec

SELECT format('CREATE ROLE fido_runtime LOGIN PASSWORD %L', :'runtime_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fido_runtime')
\gexec
SELECT format('ALTER ROLE fido_runtime LOGIN PASSWORD %L', :'runtime_password')
\gexec

ALTER ROLE fido_migrator NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
ALTER ROLE fido_runtime NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
SELECT format('GRANT fido_migrator TO %I', current_user)
\gexec

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
ALTER SCHEMA public OWNER TO fido_migrator;
GRANT CONNECT ON DATABASE fido TO fido_migrator, fido_runtime;
GRANT USAGE ON SCHEMA public TO fido_runtime;

SET ROLE fido_migrator;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO fido_runtime;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO fido_runtime;
RESET ROLE;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO fido_runtime;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO fido_runtime;

CREATE OR REPLACE FUNCTION public.prevent_runtime_custody_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $$
BEGIN
  IF session_user = 'fido_runtime' OR current_user = 'fido_runtime' THEN
    RAISE EXCEPTION 'custody events are append-only for the runtime role'
      USING ERRCODE = '42501';
  END IF;
  RETURN OLD;
END;
$$;
ALTER FUNCTION public.prevent_runtime_custody_mutation() OWNER TO fido_migrator;
REVOKE ALL ON FUNCTION public.prevent_runtime_custody_mutation() FROM PUBLIC;

DO $$
BEGIN
  IF to_regclass('public.custody_events') IS NOT NULL THEN
    DROP TRIGGER IF EXISTS custody_events_runtime_append_only ON public.custody_events;
    CREATE TRIGGER custody_events_runtime_append_only
      BEFORE UPDATE OR DELETE ON public.custody_events
      FOR EACH ROW EXECUTE FUNCTION public.prevent_runtime_custody_mutation();
  END IF;
END;
$$;
