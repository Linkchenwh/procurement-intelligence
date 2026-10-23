-- government contains the accepted observation subset, never the entire source as deduplicated spend.
SELECT COUNT(*) AS rows, COALESCE(SUM(amount), 0) AS amount,
       COUNT(DISTINCT order_key) AS orders,
       COUNT(DISTINCT CASE WHEN supplier_key <> 'UNKNOWN' THEN supplier_key END) AS supplier_codes
FROM government;
