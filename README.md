# LocalStack Console

A local development console for S3, SQS, SNS, Lambda and DynamoDB. Python + boto3 backend, plain HTML/CSS/JavaScript frontend; no frontend build step.

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

Select a resource to find its actions. Creation/update states remain visible in detail responses; refresh to check readiness. Requests display readable AWS errors. Each panel also offers a copyable resource identifier and AWS CLI (shell/PowerShell) and boto3 snippets using local credentials.

S3 and ZIP transfers are limited to 750 KB each. Source editing supports `index.handler` on Python 3.12 or Node.js 22 and **replaces the complete code package** with `index.py`/`index.js`; use ZIP upload for dependencies or other layouts. Source editing is limited to 250 KB on read. Environment JSON replaces the complete variable map, while a blank environment field keeps the current map. Functions require Lambda Docker execution support and an available runtime image. Creation can leave the dedicated console execution role behind; it has logging-only permissions.

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

Select both topics and their subscribed queues when moving fixtures to a fresh environment. Export at most 50 resources and 9 MB total; split larger selections. Lambda creation currently supports the two runtimes listed above. Exported code, environment variables and sample data are included in the downloaded JSON.

Restore asks for confirmation, stops on the first failure and displays completed steps; **there is no rollback**. Existing files/items can be overwritten. Existing Lambda creation conflicts stop restore rather than silently replacing a function. Recorded regions are retained.

## Cleanup

Delete one resource from its detail panel, or select resources across services and choose **Cleanup selected**. Bulk cleanup requires typing DELETE and separately asks whether to empty selected S3 buckets. It affects only the listed selection and reports each success/failure. Changing regions clears the selection. Emptying includes all object versions and delete markers. A nonempty bucket remains if emptying was declined. These operations are permanent.

## Verification

```sh
python -m unittest -v test_resources test_workflows test_advanced
```

The 30 backend checks cover creation, code packaging, everyday operations, configuration validation, batch messages, export/restore ordering and binary samples, cleanup validation and partial failures, filtered scans, S3 metadata and bounded downloads.

Opt-in live checks against the configured LocalStack endpoint:

```sh
python smoke_workflows.py
python smoke_lambda.py
python smoke_advanced.py
```

These create uniquely named fixtures and clean up their own resources. The advanced check covers all-service export/restore, Lambda edits, typed attributes, batch sends, filters, binary samples and versioned-bucket cleanup. Lambda tests can download runtime images and leave the standard console role behind.

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

Preview supports UTF-8 text, formatted JSON, PNG, JPEG, GIF and WebP. Text is displayed as plain text, never executed as HTML; previews truncate after 64,000 characters. File details display content type, size, ETag, version and custom metadata. The existing 750 KB download/preview limit remains; larger objects can still be listed, inspected and deleted. Raw listing/metadata responses are available in collapsed sections. Deleting a file in a versioned bucket creates a delete marker; deleting all historical versions remains a separate bucket action.
