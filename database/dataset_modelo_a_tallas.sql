DROP TABLE IF EXISTS dataset_modelo_a_tallas;

CREATE TABLE dataset_modelo_a_tallas AS
SELECT
    CAST(i.item_id     AS TEXT)  AS item_id,
    CAST(i.ticket_id   AS TEXT)  AS ticket_id,
    CAST(i.customer_id AS TEXT)  AS customer_id,   -- opcional
    LOWER(TRIM(i.canal))         AS canal,         -- muy útil
    CAST(i.sku         AS TEXT)  AS sku,           -- muy útil
    CAST(i.id_producto AS TEXT)  AS id_producto,
    LOWER(TRIM(i.categoria))     AS categoria,
    UPPER(TRIM(i.talla))         AS talla,
    CAST(i.altura_cm AS REAL)    AS altura_cm,
    CAST(i.peso_kg  AS REAL)     AS peso_kg,
    CAST(i.bmi      AS REAL)     AS bmi,
    DATETIME(i.fecha_item)       AS fecha_item,
    CAST(i.devuelto AS INTEGER)  AS devuelto
FROM items_6 i
WHERE
    i.item_id IS NOT NULL
    AND i.ticket_id IS NOT NULL
    AND i.id_producto IS NOT NULL
    AND i.categoria IS NOT NULL
    AND i.talla IS NOT NULL
    AND i.altura_cm IS NOT NULL
    AND i.peso_kg IS NOT NULL
    AND i.altura_cm BETWEEN 120 AND 230
    AND i.peso_kg  BETWEEN 30  AND 250;
