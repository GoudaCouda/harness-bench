# IPAM contract

1. Consider requests in order of increasing `prefix_len` (largest blocks
   first). Break ties by lexicographically smaller `request_id`.
2. For each request, choose the IPv4 subnet with that prefix length whose
   network address is smallest, that is contained in some pool network, and
   that does not overlap any already allocated subnet.
3. Subnets must be aligned: they are produced as children of a pool network
   at the requested prefix length.
4. If no such subnet exists, append the `request_id` to `unplaced`.
5. `allocations` maps placed `request_id`s to CIDR strings.

Do not invent identifiers. Do not announce routes.
