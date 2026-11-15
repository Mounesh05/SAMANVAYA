# F03–F06 isolated stabilization

Base: `771b41cc037ed24e2b9b763021149c49f14a2267`.
Branch: `fix/ai-provider-legacy-contracts`. No tracked source drift from the audit.
The supplied audit and all 837 specification lines were read before implementation.

1. Add regressions against real provider signature/client construction; reproduce
   node signature, timeout, parser and CI/CD format failures before fixing them.
2. Retain the factory's three parameters and JSON mode; remove unsupported
   schema keywords from Code/HR callers and validate schemas locally. The pinned
   wrapper rejects schema dictionaries as its format, as verified in the first
   implementation test. Configure the pinned
   provider's actual sync/async HTTP clients with finite 120-second transport
   timeouts, replacing the ignored keyword. Exercise local stalled HTTP responses
   and async cancellation, not live Ollama or external services.
3. Add a versioned internal strict specialist schema and legacy output adapters.
   Require substantive analysis, finite bounded numbers, known enum/field names,
   bounded lists/text/raw bytes/depth; reject malformed/unsupported data without
   filling missing scores. Preserve JSON fences/prose where unambiguous.
4. Use those contracts in all six existing nodes. Keep authorization checks,
   HR prompt filtering, output field names and the single-specialist graph.
   CI/CD uses JSON and a validated legacy section adapter. Node errors are
   sanitized explicit failure codes and never fabricated neutral success.
5. Test real generic HTTP invocation/persistence for successful, malformed,
   unavailable, timeout and unsupported responses with unchanged API keys/status
   conventions. Keep F01/F02 access/provenance and F07/F08 internal adapter defects
   explicitly deferred. No other route/service repair is included.
6. Run focused tests, existing complete backend/frontend checks, relevant native
   Mongo tests, lint/type diagnostics, diff-scope checks; document actual results
   and remaining risks, then stop for review without merge/deploy/activation.

Versioned validation limits are engineering parser bounds, not scoring policy:
64 KiB raw model response; depth 16; analysis 16,000 characters; short fields/list
items 2,000 characters; 32 items per recommendation/finding list. No raw model
output is attached to public error messages. Transport timeouts bound stalled
network reads; they are not claimed as a hard total deadline for an indefinitely
trickling stream. No detached timeout thread or new queue is introduced.
