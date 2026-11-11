# LocalStack Console

A local development console for S3, SQS, SNS, Lambda, DynamoDB, Secrets Manager and SSM Parameter Store. Python + boto3 backend, plain HTML/CSS/JavaScript frontend; no frontend build step.

See [ARCHITECTURE.md](ARCHITECTURE.md) for deployment and component diagrams, request flows, state/storage, security boundaries, limits and architectural tradeoffs.

## Run

Start an existing Docker LocalStack instance with host port 4566 published, then:

```sh
docker compose up --build -d
```

Open http://localhost:8080. Compose starts only the console and connects to `http://host.docker.internal:4566`. Both services should remain local; this development console has no authentication. It uses explicit `test` / `test` credentials and never loads your real AWS credentials.

The default region is `eu-west-2`. S3 buckets are account-wide; other resource lists are regional. Override the endpoint/default region in `.env`:

```dotenv
LOCALSTACK_ENDPOINT=http://host.docker.internal:4566
AWS_DEFAULT_REGION=eu-west-2
```

Apply changes with `docker compose up -d --force-recreate`. If the containers share a Docker network, use the LocalStack container name as the endpoint hostname. Inside a container, `localhost` addresses that container itself.

Without Docker, install Python 3.10+, run `pip install -r requirements.txt`, then `python app.py`. The default endpoint becomes `http://localhost:4566`; the console listens on `127.0.0.1:8080`.

## Daily workflows

| Service | Operations |
| --- | --- |
| S3 | Create buckets; prefix browsing and pagination; upload/download binary files; text preview; delete objects; empty buckets including all versions/delete markers; delete buckets |
| SQS | Create standard/FIFO queues; inspect attributes; send messages with typed attributes; batches of 1–10 messages; receive with attributes; acknowledge using receipt handles; change visibility; purge; delete queues |
| SNS | Create standard/FIFO topics; publish with typed attributes; list/remove subscriptions; connect SQS queues with topic-scoped queue permission; delete topics |
| Lambda | Create Python 3.12/Node.js 22 functions; invoke JSON events and inspect response/errors/logs; edit single-file source; upload ZIP code; update runtime, handler, timeout, memory and environment; delete functions |
| DynamoDB | Create on-demand tables with partition/optional sort keys; inspect schema; scan with filters; query using key expressions; paginated results; put/replace/delete typed items; delete tables |
| Secrets Manager | Create text/JSON or base64 binary secrets; inspect metadata; reveal/edit current values; list version metadata; schedule/cancel deletion; explicitly force immediate deletion |
| Parameter Store | Create hierarchical String, StringList or SecureString parameters; Standard/Advanced tiers; optional KMS key; inspect metadata; reveal/edit values; list version metadata; delete parameters |

Select a resource to find its actions. Creation/update states remain visible in detail responses; refresh to check readiness. Requests display readable AWS errors. Each panel also offers a copyable resource identifier and AWS CLI (shell/PowerShell) and boto3 snippets using local credentials.

Legacy JSON transfers, S3 previews and Lambda ZIP uploads are limited to 750 KB each. The S3 workbench streams uploads up to 100 MB per file and streams downloads without that limit. Source editing supports `index.handler` on Python 3.12 or Node.js 22 and **replaces the complete code package** with `index.py`/`index.js`; use ZIP upload for dependencies or other layouts. Source editing is limited to 250 KB on read. Environment JSON replaces the complete variable map, while a blank environment field keeps the current map. Functions require Lambda Docker execution support and an available runtime image. Creation can leave the dedicated console execution role behind; it has logging-only permissions.

SQS receive makes up to 10 messages invisible for 10 seconds and increments receive counts; it does not acknowledge them. FIFO sends use a message group and fresh deduplication IDs. Batch failures are reported individually in the response. SNS queue connections preserve existing queue policy statements. Removing a subscription does not remove its queue policy statement.

DynamoDB forms use AWS attribute-value JSON, for example `{"id":{"S":"one"},"count":{"N":"2"}}`. Deletes need the complete primary key. Scans evaluate at most 50 items per page before applying a filter; an empty page can still have a next page.

Optional auto refresh is Off by default, with 10/30/60-second choices and a last-refresh indicator. Scheduled requests do not overlap. Refresh pauses while the page is hidden, an editor is open or restore is running. Choose Off to stop it.

## Payloads, recipes and templates

Save reusable Lambda events, SQS/SNS messages (including attributes), queries and item operations using the payload controls. Saved payloads live in this browser across reloads.

The Development recipes panel records successful create, upload, item-put and subscription actions made in this console. Export these ordered steps or replay them later. The SNS-to-SQS template creates a standard topic, a queue and their subscription. Browser storage limits apply; export recipes you want to keep. Code/data and saved payloads are included in exported recipe JSON.

## Export existing resources and samples

Select resource checkboxes across services in the same region, then choose **Export selected**. This discovers existing configuration and sample data, independently of browser history. Choose **Import and run** to restore a version 2 export or an older version 1 recorded recipe. Restore orders resource creation before data/subscriptions, waits for asynchronous Lambda/table readiness and maps created identifiers.

Exports are development fixtures, not complete backups. Each export includes notes describing its bounds:

| Service | Included | Excluded |
| --- | --- | --- |
| S3 | Bucket name and up to 20 current objects, at most 750 KB each and 3 MB per bucket | Old versions, policies, lifecycle settings |
| SQS | Queue name, FIFO/deduplication, visibility, delay, retention | Messages (export never receives them), redrive and queue policies |
| SNS | Topic name/display name, FIFO/deduplication, SQS subscriptions/raw delivery | Other subscription types, filters, topic policies |
| Lambda | ZIP code, runtime, handler, memory, timeout, environment | Layers, triggers, versions, aliases, custom permissions; restore uses the console role |
| DynamoDB | Primary-key schema and first scan page (50 evaluated items), including binary attributes | Indexes, streams, TTL, table policies; restore uses on-demand billing |
| Secrets Manager | Name, description, current text/binary value and KMS key ID | Previous versions, tags, rotation and resource policies; custom keys must exist |
| Parameter Store | Name, description, type, tier, current decrypted value and KMS key ID | History, labels, tags, policies and validation patterns; custom keys must exist |

Select both topics and their subscribed queues when moving fixtures to a fresh environment. Export at most 50 resources and 9 MB total; split larger selections. Lambda creation currently supports the two runtimes listed above. Exported code, environment variables and sample data are included in the downloaded JSON.

Restore asks for confirmation, stops on the first failure and displays completed steps; **there is no rollback**. Existing files/items can be overwritten. Existing Lambda creation conflicts stop restore rather than silently replacing a function. Recorded regions are retained.

## Cleanup

Delete one resource from its detail panel, or select resources across services and choose **Cleanup selected**. Bulk cleanup requires typing DELETE and separately asks whether to empty selected S3 buckets. It affects only the listed selection and reports each success/failure. Changing regions clears the selection. Emptying includes all object versions and delete markers. A nonempty bucket remains if emptying was declined. Secrets Manager cleanup schedules deletion with a seven-day recovery window; the secret remains listed and can be restored. Other cleanup operations are permanent. Immediate secret deletion requires the explicit checkbox in its individual delete form.

## Secret and parameter values

Lists and default details show metadata only. **Reveal value** opens the current value in a dialog; closing it clears the displayed value. **Update value** loads the current value for editing and saves a new version. SSM updates preserve the parameter type, tier and encryption settings. History views show version metadata without values.

Secret and parameter actions are excluded from browser recipe recording and saved payload controls. **Export selected** supports both services, but asks explicitly before including plaintext secret/decrypted parameter values; the backend also requires the opt-in flag. Binary secrets are exported as base64, which is not encryption. Imports restore the current value as a new resource, preserving type/tier and requiring any custom KMS key to exist. Existing names cause a creation conflict rather than overwriting a value. This console still uses only the configured local endpoint and test credentials.

## Verification

```sh
python -m unittest -v test_resources test_workflows test_advanced test_configuration test_developer
```

The 61 backend checks cover creation, code packaging, everyday operations, configuration validation, batch messages, export/restore ordering and binary samples, cleanup validation and partial failures, filtered scans, S3 metadata and bounded downloads, secret/parameter values and versions, recovery defaults and export consent.

Opt-in live checks against the configured LocalStack endpoint:

```sh
python smoke_workflows.py
python smoke_lambda.py
python smoke_advanced.py
python smoke_configuration.py
```

These create uniquely named fixtures and clean up their own resources. The advanced check covers the original five-service export/restore, Lambda edits, typed attributes, batch sends, filters, binary samples and versioned-bucket cleanup. The configuration check covers both new services over HTTP, text/binary values, all parameter types, updates/history, deletion recovery and export/restore. Lambda tests can download runtime images and leave the standard console role behind.

Frontend logic checks use jsdom in a separate test-only directory; no browser runtime dependency is added:

```powershell
npm install --prefix "$env:TEMP/localstack-console-qa" --no-save --package-lock=false jsdom
node test_frontend.cjs "$env:TEMP/localstack-console-qa/node_modules"
```

## Troubleshooting and stop

```sh
curl http://localhost:4566/_localstack/health
docker compose logs console
docker compose down
```

Stopping Compose stops only the console. Your separately started LocalStack container is unaffected. If lists are empty, check the selected region and test account. LocalStack version/edition can affect runtime and service support.

### S3 file browser

Selecting a bucket opens a file table (cards on narrow screens) with object keys, sizes, modification dates and actions on each file: preview, download, details, copy key and delete. Key-prefix filtering and previous/next pages are available, with 100 objects per page. Upload suggests an object key from the selected filename and current prefix; successful uploads, deletes and empty-bucket actions refresh the file list in place.

Preview supports UTF-8 text, formatted JSON, PNG, JPEG, GIF and WebP. Text is displayed as plain text, never executed as HTML; previews truncate after 64,000 characters. File details display content type, size, ETag, version and custom metadata. Previews remain limited to 750 KB; downloads stream directly, including larger objects. Larger files can also be inspected and deleted. Raw listing/metadata responses are available in collapsed sections. Deleting a file in a versioned bucket creates a delete marker; deleting all historical versions remains a separate bucket action.

## Developer workbenches

All seven services now have additional testing/debugging tools:

| Service | Developer tools |
| --- | --- |
| S3 | Folder navigation/breadcrumbs; multiple-file chooser or drag-and-drop with progress and per-file results; raw streamed uploads up to 100 MB each; streamed downloads; UTF-8/JSON editing up to 1 MB with ETag checks; version listing/restore; bucket versioning; presigned GET/PUT URLs (up to one hour) |
| SQS | Explicit-receive message inbox with body/attributes/receive counts; per-message acknowledgement, release/visibility and edited resend; queue settings; DLQ configuration; native redrive task start/list/cancel; navigation to connected Lambda consumers |
| SNS | Topic-to-subscription routes; message-attribute or JSON-body filter editor; raw-delivery settings; test publishing and navigation to destination inboxes |
| Lambda | JSON invocation workbench, response/logs, server round-trip and reported execution duration; latest 10 runs and response comparisons; saved input events; environment key/value editor; immutable versions/aliases; SQS event source mapping create/enable/disable/remove |
| DynamoDB | Item table with typed cells and expandable documents; conditional single-attribute edits; full-document editor; query builder with sort conditions and index choice; global secondary index creation; JSON fixture import (1–100 typed items) with per-item outcomes |
| Secrets Manager | Typed JSON field editor; explicit reveal/compare of historical versions; rollback by moving AWSCURRENT; staging-label assignment/movement |
| Parameter Store | Metadata-only hierarchy browser; select a whole path for export; JSON or literal .env import (up to 100 entries); relative-name environment comparisons with optional decrypted-value equality checking; historical-value comparison/restore; version labels |

The SQS inbox never receives in the background. Opening a queue only loads its metadata and tools. Receiving is explicit and affects visibility/counts; resending creates a new copy and leaves the original message until it is acknowledged. Native redrive requires the selected source to be a dead-letter queue.

The SNS filter editor updates AWS subscription attributes in separate calls. If an update fails partway, refresh to inspect the applied settings. Use **Publish test event**, then **Open destination inbox** and explicitly receive messages to inspect actual delivery. Opening a Lambda trigger can consume queued messages: the console asks before enabling it, and does not broaden the execution role's permissions. That role needs the appropriate SQS permissions.

Invocation histories exist only in this page's memory and contain events, responses and logs. Closing/reloading the page clears them; **Save event** explicitly stores input in browser payload storage. Execution duration comes from returned REPORT logs when present; round-trip timing is measured by the console backend. Auto refresh pauses while an editor/dialog is open or the workbench has focus.

Single-cell DynamoDB edits use UpdateItem with a condition comparing the original attribute, preserving other fields and detecting concurrent edits. Full-document saves and imports replace matching items after confirmation. Key attributes cannot be changed in place. Binary attributes use base64 in typed JSON. Index creation is asynchronous; refresh until the index is ACTIVE before querying it.

S3 transfers stream through the local console rather than embedding files in JSON. Successful uploads remain if later files fail or the batch is stopped. Larger streamed uploads are not recorded in browser recipes. Text edits preserve custom metadata/content type and send conditional ETag writes; historical restoration preserves the selected version's metadata and creates a new current object. Presigned URLs use the public LocalStack endpoint (the default Docker hostname maps to localhost), not the console URL. Previews still have the 750 KB limit, while streamed downloads have no console-imposed file-size limit. Legacy JSON transfer and Lambda ZIP limits remain unchanged.

Configuration workbenches fetch historical secret/parameter values only after an explicit reveal, compare or edit action. Values are not stored in browser recipes. Parameter environment comparison defaults to metadata; its optional value check returns equality only, not plaintext values. .env import accepts literal KEY=value lines, optional surrounding quotes and comments; it does not evaluate shell expansion. Use the existing **Export selected** action for JSON export, with explicit plaintext-value consent.

**Verified LocalStack 4.0.3 limitation:** assigning/moving parameter labels works, but UnlabelParameterVersion is not implemented. The removal action reports that limitation rather than claiming success. Removal code is present for LocalStack versions that support the API.

### Workbench verification

```sh
python -m unittest -v test_resources test_workflows test_advanced test_configuration test_developer
python smoke_developer.py
```

The 61 backend tests and expanded frontend suite cover validation, ownership checks, conditional edits, binary values, bounded streaming, recovery and the new GUI flows. The opt-in live script creates unique fixtures and removes them afterward; it verifies multipart streamed transfers, S3 restore, native DLQ redrive, filtered SNS delivery, DynamoDB index queries, secret/parameter rollback, Lambda aliases and SNS → SQS → Lambda → DynamoDB. It creates a fixture-only execution role and cleans it up as well.
