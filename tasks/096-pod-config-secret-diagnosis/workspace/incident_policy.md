# Invoice platform incident policy

Authoritative precedence is current generation plus `image_contract.json`, current configuration/secret inventory, then current-generation events. Historical healthy observations do not override the new image contract.

Allowed repair fields are only: ExternalSecret remote `version` and `property`; Deployment HTTP_PORT ConfigMap `name`; Deployment readiness HTTP path; Service `targetPort`. Preserve every other field byte-equivalently at the parsed-object level. The Service must use a named target port. Never copy secret values. A local simulator is evidence only, not a live rollout. Rollback restores the five original leaf fields across those four repair groups; deleting or scaling the workload is prohibited.
