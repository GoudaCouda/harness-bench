DROP TABLE IF EXISTS refunds;
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
  customer_id TEXT PRIMARY KEY,
  customer_name TEXT NOT NULL,
  region TEXT NOT NULL
);

CREATE TABLE products (
  product_id TEXT PRIMARY KEY,
  product_name TEXT NOT NULL,
  category TEXT NOT NULL
);

CREATE TABLE orders (
  order_id TEXT PRIMARY KEY,
  customer_id TEXT NOT NULL,
  order_date TEXT NOT NULL,
  status TEXT NOT NULL
);

CREATE TABLE order_items (
  order_id TEXT NOT NULL,
  line_id TEXT NOT NULL,
  product_id TEXT NOT NULL,
  quantity INTEGER NOT NULL,
  unit_price NUMERIC NOT NULL,
  discount_amount NUMERIC NOT NULL,
  PRIMARY KEY (order_id, line_id)
);

CREATE TABLE refunds (
  refund_id TEXT PRIMARY KEY,
  order_id TEXT NOT NULL,
  line_id TEXT NOT NULL,
  refund_date TEXT NOT NULL,
  amount NUMERIC NOT NULL,
  status TEXT NOT NULL
);

INSERT INTO customers VALUES
('C001','Ada Chen','North'),
('C002','Ben Ortiz','West'),
('C003','Cleo Singh','North'),
('C004','Dara Moore','East'),
('C005','Eli Park','South'),
('C006','Farah King','East');

INSERT INTO products VALUES
('P101','Atlas Laptop','Hardware'),
('P102','Nova Monitor','Hardware'),
('P103','Ergo Desk','Furniture'),
('P104','USB-C Dock','Accessories'),
('P105','Arc Chair','Furniture'),
('P106','Priority Support Plan','Services'),
('P107','Conference Webcam','Accessories'),
('P108','Standing Desk','Furniture'),
('P109','Security Add-on','Services'),
('P110','Mechanical Keyboard','Accessories');

INSERT INTO orders VALUES
('O2001','C001','2025-01-05','paid'),
('O2002','C002','2025-02-10','paid'),
('O2003','C003','2025-03-15','cancelled'),
('O2004','C001','2025-04-02','paid'),
('O2005','C004','2025-03-20','partially_refunded'),
('O2006','C003','2025-01-01','paid'),
('O2007','C004','2025-03-31','paid'),
('O2008','C002','2024-12-31','paid'),
('O2009','C001','2025-04-01','paid'),
('O2010','C005','2025-02-28','returned'),
('O2011','C005','2025-02-15','paid'),
('O2012','C006','2025-03-01','pending'),
('O2013','C002','2025-03-25','partially_refunded'),
('O2014','C006','2025-01-18','paid'),
('O2015','C003','2025-02-04','partially_refunded'),
('O2016','C004','2025-02-20','paid'),
('O2017','C001','2025-03-08','paid'),
('O2018','C005','2025-03-30','paid'),
('O2019','C002','2025-03-12','cancelled'),
('O2020','C006','2025-01-22','paid'),
('O2021','C003','2025-02-14','paid'),
('O2022','C004','2025-03-02','partially_refunded'),
('O2023','C001','2024-12-28','paid'),
('O2024','C005','2025-04-03','paid'),
('O2025','C002','2025-02-26','returned'),
('O2026','C006','2025-03-31','paid'),
('O2027','C003','2025-01-01','partially_refunded'),
('O2028','C004','2025-01-29','paid'),
('O2029','C001','2025-03-18','pending'),
('O2030','C005','2025-02-08','paid');

INSERT INTO order_items VALUES
('O2001','L1','P101',1,1200.00,100.00),
('O2001','L2','P104',2,160.00,20.00),
('O2002','L1','P102',3,300.00,60.00),
('O2003','L1','P101',1,5000.00,0.00),
('O2004','L1','P103',2,900.00,0.00),
('O2005','L1','P102',1,320.00,20.00),
('O2005','L2','P103',1,500.00,50.00),
('O2006','L1','P101',1,100.00,0.00),
('O2007','L1','P104',2,150.00,0.00),
('O2008','L1','P102',10,100.00,0.00),
('O2009','L1','P101',1,1000.00,0.00),
('O2010','L1','P102',5,999.00,0.00),
('O2011','L1','P105',2,140.00,30.00),
('O2012','L1','P106',3,500.00,0.00),
('O2013','L1','P106',2,200.00,0.00),
('O2014','L1','P107',4,90.00,20.00),
('O2014','L2','P104',3,155.00,15.00),
('O2015','L1','P101',2,1150.00,100.00),
('O2015','L2','P109',2,180.00,20.00),
('O2016','L1','P108',1,850.00,75.00),
('O2016','L2','P105',4,135.00,40.00),
('O2017','L1','P102',2,310.00,20.00),
('O2017','L2','P110',5,85.00,25.00),
('O2018','L1','P106',3,210.00,30.00),
('O2019','L1','P101',4,1200.00,0.00),
('O2019','L2','P103',3,800.00,0.00),
('O2020','L1','P107',2,95.00,0.00),
('O2020','L2','P110',3,90.00,10.00),
('O2021','L1','P103',1,780.00,80.00),
('O2021','L2','P104',2,160.00,20.00),
('O2022','L1','P102',3,295.00,35.00),
('O2022','L2','P107',5,88.00,20.00),
('O2023','L1','P108',2,900.00,0.00),
('O2023','L2','P109',1,200.00,0.00),
('O2024','L1','P101',1,1300.00,0.00),
('O2025','L1','P102',6,300.00,0.00),
('O2025','L2','P104',10,150.00,0.00),
('O2026','L1','P108',1,820.00,20.00),
('O2026','L2','P106',2,205.00,10.00),
('O2027','L1','P101',1,1180.00,80.00),
('O2027','L2','P109',3,175.00,25.00),
('O2028','L1','P105',3,145.00,15.00),
('O2029','L1','P107',20,90.00,0.00),
('O2030','L1','P110',2,95.00,0.00),
('O2030','L2','P103',1,760.00,60.00);

INSERT INTO refunds VALUES
('R3001','O2005','L1','2025-03-28',50.00,'completed'),
('R3002','O2005','L1','2025-04-02',25.00,'completed'),
('R3003','O2005','L2','2025-03-29',100.00,'pending'),
('R3004','O2007','L1','2025-04-09',100.00,'completed'),
('R3005','O2013','L1','2025-04-07',80.00,'completed'),
('R3006','O2011','L1','2025-03-10',10.00,'declined'),
('R3007','O2010','L1','2025-03-02',200.00,'completed'),
('R3008','O2015','L1','2025-04-01',60.00,'completed'),
('R3009','O2015','L1','2025-04-06',30.00,'completed'),
('R3010','O2015','L2','2025-03-21',40.00,'pending'),
('R3011','O2022','L1','2025-04-07',45.00,'completed'),
('R3012','O2022','L2','2025-04-08',50.00,'completed'),
('R3013','O2027','L1','2025-03-20',25.00,'completed'),
('R3014','O2027','L2','2025-03-25',15.00,'declined'),
('R3015','O2030','L1','2025-04-04',10.00,'completed');
