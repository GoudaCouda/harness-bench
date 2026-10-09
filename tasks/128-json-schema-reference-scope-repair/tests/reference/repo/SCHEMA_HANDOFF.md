# Catalog schema migration handoff

The bundle remains entirely offline and no schema was published or deployed. I treated each registry entry as the retrieval URI and then resolved the resource's '$id' to obtain its effective base. The order file still declared the pre-migration absolute identifier under 'https://schemas.example/orders/', so its relative address reference escaped the registered 'https://schemas.example/catalog/' bundle even though the files were adjacent on disk.

I changed only 'schemas/orders/order.json': its '$id' is now the relative value 'order.json'. Against the protected retrieval URI this produces 'https://schemas.example/catalog/orders/order.json'. The unchanged '../common/address.json#address' reference then resolves to the registered address resource and its 'address' anchor. Catalog-to-order and order-to-address are both closed.

Verification used 'python3 tools/check_bundle.py' before and after the repair and 'python3 tools/check_bundle.py --write' for the durable audit. The final report has three resources, one anchor, two resolved edges, no unresolved references, and valid=true. 'examples/order-valid.json' is true while 'examples/order-missing-address.json' remains false, proving that required address constraints were not weakened.
