-- Must return zero rows on validated practice inputs.
SELECT PO_ID FROM orders WHERE Quantity <= 0 OR amount < 0 OR Supplier IS NULL;
