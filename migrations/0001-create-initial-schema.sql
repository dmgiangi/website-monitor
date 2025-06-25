CREATE SCHEMA website_monitor;

SET search_path TO website_monitor;

CREATE OR REPLACE FUNCTION is_valid_regex(pattern TEXT)
    RETURNS BOOLEAN AS
$$
BEGIN
    -- Tenta di usare il pattern in un'operazione.
    -- Se il pattern non è valido, PostgreSQL solleverà un'eccezione.
    PERFORM '' ~ pattern;
    RETURN TRUE;
EXCEPTION
    -- Se l'eccezione specifica viene sollevata, la catturiamo...
    WHEN invalid_regular_expression THEN
        -- ...e restituiamo FALSE, indicando che la validazione è fallita.
        RETURN FALSE;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

CREATE DOMAIN valid_regex AS TEXT
    CHECK ( is_valid_regex(VALUE) );

CREATE TABLE monitored_targets
(
    id              SERIAL PRIMARY KEY,
    url TEXT NOT NULL CHECK (url ~* '^https?://[a-zA-Z0-9.-]+(:\d+)?(/.*)?$'),
    method          TEXT     NOT NULL CHECK (method ~* 'GET|POST|PUT|DELETE|PATCH'),
    check_interval  INTERVAL NOT NULL,
    default_headers JSONB,
    regex_pattern   valid_regex
);

CREATE TABLE target_leases
(
    monitored_target_id INTEGER PRIMARY KEY REFERENCES monitored_targets (id) ON DELETE CASCADE,
    next_fire_at        TIMESTAMPTZ NOT NULL,
    worker_id           TEXT,
    lease_acquired_at   TIMESTAMPTZ
);

CREATE INDEX idx_target_leases_next_fire_at ON target_leases (next_fire_at);

CREATE OR REPLACE FUNCTION propagate_lease_on_target_change()
    RETURNS TRIGGER AS
$$
BEGIN
    IF (TG_OP = 'INSERT') THEN
        INSERT INTO target_leases (monitored_target_id, next_fire_at)
        VALUES (NEW.id, NOW());

    ELSIF (TG_OP = 'UPDATE') THEN
        IF OLD.check_interval IS DISTINCT FROM NEW.check_interval THEN
            UPDATE target_leases
            SET next_fire_at = NOW()
            WHERE monitored_target_id = NEW.id;
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_monitored_targets_lease_propagation ON monitored_targets;

CREATE TRIGGER trigger_monitored_targets_lease_propagation
    AFTER INSERT OR UPDATE
    ON monitored_targets
    FOR EACH ROW
EXECUTE FUNCTION propagate_lease_on_target_change();