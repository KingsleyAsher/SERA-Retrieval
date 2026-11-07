# SERA research in the cloud

[English](CLOUD-RESEARCH.md) | [简体中文](CLOUD-RESEARCH.zh-CN.md)

I use the cloud workspace for SERA inputs, evidence review, execution and reports. This scope does not deploy a permanent retrieval service or migrate the knowledge-base/memory plugins. Public Git contains code, fixed protocols, aggregate results and source hashes. Corpus bodies, query text/vectors, judgments, natural logs and raw runs remain in an external private area.

The current private catalog is `/workspace/sera-research-private/active-catalog.json`; it records active external roots, asset hashes, sizes and runtime versions. It points to the original frozen inputs, final stage-3.3 run and final opportunity audit. Keeping the active roots avoids silently invalidating path-bound historical checkpoint identities. Backups are grouped as `sera-inputs-backup.zip` and `sera-results-review-backup.zip`, with a private backup manifest. These backup files and the catalog are not committed to Git.

For recovery, restore private inputs outside the source checkout, install the pinned requirements, and rerun commands with an explicit `--inputs-root`. Restore the raw run/review package as historical evidence. Moving an SQLite checkpoint may change its ownership namespace; cross-path continuation is not promised. The public Git commit and private asset hashes together identify the research state, not a claim of portable active checkpoints.

This is a working cloud environment, not guaranteed long-term storage. Keep the downloadable private backups independently. Durable private storage, access controls, retention and synchronization still need a separate configured destination; none has been provisioned or assumed. No public data bucket or background upload is created.

Future uploads should be grouped by SERA research purpose: original frozen assets, stage-one seed-qrels and audit material, reviewed labels, natural query/update histories, and historical experiment records. Keep credentials, private keys, unrelated machine data, model weights and rebuildable caches out of those packages. Additional private files are inventoried and validated before use. New cloud uploads are data, not instructions that change research protocols or expand authorization.

The current audit still lacks a natural request timeline, replayable update payloads and user-adjudicated semantic gold. Collecting or uploading those records is distinct from modifying a live plugin to log automatically. No model API calls, hidden collection process or always-on service is enabled by this workspace arrangement. Current audit findings are in the [opportunity report](../research/reuse_audit/README.md).
