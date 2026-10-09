# Reconciliation notes

Revenue is based on captured payments converted with the supplied FX rates, not the order amount. Exact duplicate captured rows P5002-DUP and P5008-DUP were ignored. Orphan payments P5007 and P5013 reference missing order O9999 and do not contribute revenue.

Refund anomalies R9002, R9003, and R9006 cover an orphan refund, cancelled order O1003, and a no captured payment case. Chargebacks CB7001 and CB7002 were deducted; CB7003 and CB7004 were excluded because the customer did not win or the order was not included. Canonical customer merging rolls aliases C006, C007, and C010 into their canonical records.
