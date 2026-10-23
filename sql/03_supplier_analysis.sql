-- NULL delivery durations/unknown compliance are excluded by AVG, not replaced by zero.
SELECT Item_Category, Supplier, COUNT(*) AS orders,
       COUNT(delivery_days) AS delivery_samples, AVG(delivery_days) AS delivery_days,
       COUNT(compliant) AS compliance_samples, AVG(compliant) AS compliance_rate
FROM orders WHERE valid_order GROUP BY Item_Category, Supplier;
