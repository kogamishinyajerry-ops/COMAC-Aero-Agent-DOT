# Adapter review before heldout exposure

The first independent static review identified objective, task-identity consistency, CAD source provenance, actual solver counting, rejection retention and end-time budget acceptance gaps. They were fixed before initialization of the development session. The protocol was not changed.

Reviewed final adapter SHA-256: `0898baa98b80b0217bf7a435a5f2aa0cf8f30f1f4ba6ec924564145a8ecec262`. Nine focused unit tests passed. The reviewer did not access heldout material.

Two conservative false-negative limitations remain and are disclosed rather than silently revising the running trial:

1. A task where all nine candidates pass, with three or four cases, cannot establish the no-rejection waiver within the 24-solver budget. Such a task may produce a valid design but the current automatic acceptance refuses it.
2. A lower-mass candidate passing every primary case continues to block a heavier selected candidate even if later refinement/CAD evidence invalidates the lower-mass candidate. The current automatic acceptance is conservative and cannot resolve that case.

These are restrictions of this trial adapter, not physics findings. No claim is made that every allowed task instance can be completed. The independent heldout evaluator must report any effect on the actual trial rather than alter requirements to bypass a restriction.

The local hashes and declarations are audit aids, not signatures or proof of a native model's identity. The independent task commitment and actual conversation tool calls are the external evidence. No proprietary model family is identified by this record.
