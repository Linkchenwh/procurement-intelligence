-- No mutation: investigate duplicate order keys before any aggregation.
SELECT PO_ID, COUNT(*) AS rows_per_order
FROM orders GROUP BY PO_ID HAVING COUNT(*) > 1;
