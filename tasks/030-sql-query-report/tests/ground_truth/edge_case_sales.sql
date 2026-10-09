CREATE TABLE customers (customer_id TEXT PRIMARY KEY, customer_name TEXT NOT NULL, region TEXT NOT NULL);
CREATE TABLE products (product_id TEXT PRIMARY KEY, product_name TEXT NOT NULL, category TEXT NOT NULL);
CREATE TABLE orders (order_id TEXT PRIMARY KEY, customer_id TEXT NOT NULL, order_date TEXT NOT NULL, status TEXT NOT NULL);
CREATE TABLE order_items (order_id TEXT NOT NULL, line_id TEXT NOT NULL, product_id TEXT NOT NULL, quantity INTEGER NOT NULL, unit_price NUMERIC NOT NULL, discount_amount NUMERIC NOT NULL, PRIMARY KEY (order_id, line_id));
CREATE TABLE refunds (refund_id TEXT PRIMARY KEY, order_id TEXT NOT NULL, line_id TEXT NOT NULL, refund_date TEXT NOT NULL, amount NUMERIC NOT NULL, status TEXT NOT NULL);

INSERT INTO customers VALUES ('EC1','Elm Ltd','East'),('EC2','Fir Ltd','West');
INSERT INTO products VALUES
('EP1','Shared Label','Hardware'),('EP2','Shared Label','Accessories'),
('EP3','Desk','Furniture'),('EP4','Support','Services');
INSERT INTO orders VALUES
('E100','EC1','2025-01-01','paid'),('E101','EC2','2025-03-31','partially_refunded'),
('E102','EC1','2025-03-15','paid'),('E103','EC2','2025-04-02','cancelled'),
('E104','EC2','2024-12-31','paid');
INSERT INTO order_items VALUES
('E100','L1','EP1',1,500.00,0.00),('E100','L2','EP3',1,100.00,0.00),
('E101','L1','EP2',2,300.00,50.00),('E102','L1','EP4',2,250.00,0.00),
('E103','L1','EP1',10,999.00,0.00),('E104','L1','EP2',10,999.00,0.00);
INSERT INTO refunds VALUES
('ER1','E101','L1','2025-03-25',20.00,'completed'),
('ER2','E101','L1','2025-04-07',30.00,'completed'),
('ER3','E102','L1','2025-03-20',100.00,'pending'),
('ER4','E102','L1','2025-04-08',50.00,'completed');
