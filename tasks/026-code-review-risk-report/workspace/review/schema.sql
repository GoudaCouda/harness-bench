create table export_jobs (
    id text primary key,
    tenant_id text not null,
    request_token text not null,
    requested_by text not null,
    include_pii integer not null default 0,
    state text not null check (state in ('queued', 'running', 'complete', 'failed')),
    lease_owner text,
    lease_until text,
    object_key text not null,
    object_etag text,
    checksum text,
    created_at text not null,
    unique (tenant_id, request_token)
);

create index export_jobs_claim_order
    on export_jobs (state, created_at, id);
