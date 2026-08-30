-- Read-only sample queries.
-- Monthly spend
SELECT substr(date,1,7) AS month, ROUND(SUM(total),2) AS spend_eur FROM receipts GROUP BY month;
-- Category spend
SELECT category, ROUND(SUM(COALESCE(line_total,price)),2) AS spend_eur FROM items GROUP BY category;
-- Store comparison
SELECT COALESCE(NULLIF(trim(i.canonical_name),''),i.name) AS product,r.store,i.normalized_price_unit,AVG(i.normalized_unit_price) AS average_price
FROM items i JOIN receipts r ON r.id=i.receipt_id WHERE i.normalized_unit_price>0
GROUP BY product,r.store,i.normalized_price_unit;
-- Normalized unit-price history
SELECT r.date,COALESCE(NULLIF(trim(i.canonical_name),''),i.name) AS product,r.store,i.normalized_unit_price,i.normalized_price_unit
FROM items i JOIN receipts r ON r.id=i.receipt_id WHERE i.normalized_unit_price>0 ORDER BY product,r.date DESC;
-- Recurring products
SELECT COALESCE(NULLIF(trim(canonical_name),''),name) AS product,COUNT(DISTINCT receipt_id) AS receipts
FROM items GROUP BY product HAVING receipts>1;
-- Price confidence/source distribution
SELECT COALESCE(price_parse_source,'missing') AS source,price_parse_confidence,COUNT(*) AS items
FROM items GROUP BY source,price_parse_confidence;
