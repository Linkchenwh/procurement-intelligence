-- Input orders is validated at one row per PO_ID; amount is order value, not payment.
SELECT SUM(amount) AS raw_amount,
       SUM(CASE WHEN valid_order THEN amount ELSE 0 END) AS valid_amount,
       SUM(CASE WHEN NOT valid_order THEN amount ELSE 0 END) AS cancelled_amount,
       SUM(CASE WHEN delivered_order THEN amount ELSE 0 END) AS delivered_amount,
       COUNT(DISTINCT PO_ID) AS order_count,
       COUNT(DISTINCT CASE WHEN valid_order THEN PO_ID END) AS valid_order_count,
       COUNT(DISTINCT CASE WHEN valid_order THEN Supplier END) AS supplier_count
FROM orders;
