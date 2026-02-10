
DROP TABLE IF EXISTS base_modelo_devoluciones;


CREATE TABLE base_modelo_devoluciones AS
SELECT
    -- Identificadores (solo para merges y cálculos)
    i.item_id,
    i.ticket_id,
    i.customer_id,
    i.id_producto,
    i.sku,
-- Datos de la venta
    i.canal,
    i.store_id,
    i.provincia AS provincia_tienda,
    i.fecha_item AS fecha_compra,
    i.descuento_pct AS descuento,
    i.precio_neto_unit AS precio_neto,
    i.coste_bruto,
    i.margen_unit AS margen,
    i.promotion_id,
    i.devuelto,
-- Datos del cliente
    c.provincia AS provincia_cliente,
    c.comunidad,
    c.fecha_primer_compra,
    c.fecha_ultima_compra,
    c.n_pedidos,
    c.n_items_comprados,
    c.anio_nacimiento,
    c.edad_alta,
-- Datos físicos del cliente
    i.altura_cm,
    i.peso_kg,
-- Datos del producto
    i.categoria,
    i.color,
    i.talla
FROM items_6 i
LEFT JOIN clientes c ON i.customer_id = c.customer_id;
