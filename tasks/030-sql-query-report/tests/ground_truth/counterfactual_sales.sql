CREATE TABLE customers (customer_id TEXT PRIMARY KEY, customer_name TEXT NOT NULL, region TEXT NOT NULL);
CREATE TABLE products (product_id TEXT PRIMARY KEY, product_name TEXT NOT NULL, category TEXT NOT NULL);
CREATE TABLE orders (order_id TEXT PRIMARY KEY, customer_id TEXT NOT NULL, order_date TEXT NOT NULL, status TEXT NOT NULL);
CREATE TABLE order_items (order_id TEXT NOT NULL, line_id TEXT NOT NULL, product_id TEXT NOT NULL, quantity INTEGER NOT NULL, unit_price NUMERIC NOT NULL, discount_amount NUMERIC NOT NULL, PRIMARY KEY (order_id, line_id));
CREATE TABLE refunds (refund_id TEXT PRIMARY KEY, order_id TEXT NOT NULL, line_id TEXT NOT NULL, refund_date TEXT NOT NULL, amount NUMERIC NOT NULL, status TEXT NOT NULL);

INSERT INTO customers VALUES
('HC1','Aster Ltd','North'),('HC2','Birch Ltd','South'),('HC3','Cedar Ltd','East'),('HC4','Dune Ltd','West');
INSERT INTO products VALUES
('HP1','Alpha Device','Hardware'),('HP2','Beta Cable','Accessories'),('HP3','Gamma Desk','Furniture'),('HP4','Delta Plan','Services');
INSERT INTO orders VALUES
('H100','HC1','2025-01-01','paid'),('H101','HC2','2025-03-31','partially_refunded'),
('H102','HC3','2025-02-01','cancelled'),('H103','HC4','2024-12-31','paid'),
('H104','HC4','2025-04-01','paid'),('H105','HC3','2025-02-10','paid');
INSERT INTO order_items VALUES
('H100','L1','HP1',2,250.00,20.00),('H100','L2','HP2',1,80.00,0.00),
('H101','L1','HP2',4,75.00,10.00),('H102','L1','HP3',1,2000.00,0.00),
('H103','L1','HP1',9,999.00,0.00),('H104','L1','HP4',1,900.00,0.00),
('H105','L1','HP3',1,500.00,50.00),('H105','L2','HP4',2,100.00,0.00);
INSERT INTO refunds VALUES
('HR1','H101','L1','2025-04-01',40.00,'completed'),
('HR2','H105','L1','2025-04-05',25.00,'completed'),
('HR3','H105','L2','2025-04-03',50.00,'pending');
