-- SurgiTwin-RTA nightly hash chain verification (SRS FR-DAT-005)
-- Origin: BioSync-Gateway database/migrations/hash-chain-check.sql (adapted)
-- Recomputes every audit_log digest with audit_chain_digest() and checks prev_hash
-- linkage with a window function. Read-only. Schedule with cron or pgAgent.
-- Not applied at database initialization. Run it against the compliance database.
--
-- Adaptation: the Gateway recomputed hashes inline with timestamp::TEXT, which depends on
-- the session TimeZone and did not match the trigger. This version calls the same
-- audit_chain_digest() function as the trigger and verify_hash_chain().

SET search_path TO public;

WITH chain AS (
    SELECT
        id,
        table_name,
        occurred_at,
        actor_id,
        data_prev,
        data_new,
        reason,
        prev_hash,
        current_hash,
        LAG(current_hash) OVER (ORDER BY id) AS expected_prev_hash,
        audit_chain_digest(prev_hash, occurred_at, actor_id, data_prev, data_new, reason) AS recomputed_hash
    FROM audit_log
),
checked AS (
    SELECT
        *,
        (prev_hash = COALESCE(expected_prev_hash,
                              '0000000000000000000000000000000000000000000000000000000000000000')) AS prev_hash_valid,
        (recomputed_hash = current_hash) AS current_hash_valid
    FROM chain
)
SELECT
    'Hash Chain Verification Report' AS report_title,
    NOW() AS verification_timestamp,
    COUNT(*) AS total_entries,
    SUM(CASE WHEN prev_hash_valid AND current_hash_valid THEN 1 ELSE 0 END) AS valid_entries,
    SUM(CASE WHEN NOT (prev_hash_valid AND current_hash_valid) THEN 1 ELSE 0 END) AS broken_entries,
    CASE
        WHEN SUM(CASE WHEN NOT (prev_hash_valid AND current_hash_valid) THEN 1 ELSE 0 END) = 0
        THEN 'OK'
        ELSE 'BROKEN'
    END AS integrity_status,
    MIN(CASE WHEN NOT (prev_hash_valid AND current_hash_valid) THEN id END) AS first_broken_id,
    jsonb_agg(
        jsonb_build_object(
            'id', id,
            'table_name', table_name,
            'prev_hash_valid', prev_hash_valid,
            'current_hash_valid', current_hash_valid,
            'stored_hash', current_hash,
            'computed_hash', recomputed_hash
        )
    ) FILTER (WHERE NOT (prev_hash_valid AND current_hash_valid)) AS broken_entries_detail
FROM checked;

-- Entries by table
SELECT
    table_name,
    COUNT(*) AS entry_count,
    MIN(occurred_at) AS first_entry,
    MAX(occurred_at) AS last_entry
FROM audit_log
GROUP BY table_name
ORDER BY table_name;
