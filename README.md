# tap-invoiced

This is a [Singer](https://singer.io) tap that produces JSON-formatted data
following the [Singer
spec](https://github.com/singer-io/getting-started/blob/master/SPEC.md).

This tap:

- Pulls raw data from [Invoiced](https://invoiced.com)
- Extracts the following resources:
  - [Credit Notes](https://invoiced.com/docs/api/#credit-note-object)
  - [Customers](https://invoiced.com/docs/api/#customer-object)
  - [Estimates](https://invoiced.com/docs/api/#estimate-object)
  - [Invoices](https://invoiced.com/docs/api/#invoice-object)
  - [Plans](https://invoiced.com/docs/api/#plan-object)
  - [Subscriptions](https://invoiced.com/docs/api/#subscription-object)
- Outputs the schema for each resource
- Incrementally pulls data based on the input state

---

## Streams

| Stream | API Documentation | Key Properties | Replication Key | Replication Method |
|---|---|---|---|---|
| `credit_notes` | [Credit Note](https://invoiced.com/docs/api/#credit-note-object) | `id` | `updated_at` | INCREMENTAL |
| `customers` | [Customer](https://invoiced.com/docs/api/#customer-object) | `id` | `updated_at` | INCREMENTAL |
| `estimates` | [Estimate](https://invoiced.com/docs/api/#estimate-object) | `id` | `updated_at` | INCREMENTAL |
| `invoices` | [Invoice](https://invoiced.com/docs/api/#invoice-object) | `id` | `updated_at` | INCREMENTAL |
| `plans` | [Plan](https://invoiced.com/docs/api/#plan-object) | `id` | `updated_at` | INCREMENTAL |
| `subscriptions` | [Subscription](https://invoiced.com/docs/api/#subscription-object) | `id` | `updated_at` | INCREMENTAL |

---

## Configuration

### Required Config Keys

| Key | Type | Description |
|---|---|---|
| `api_key` | string | Invoiced API key. Generate one from **Settings → API Keys** in the Invoiced dashboard. |
| `start_date` | string | ISO 8601 date — only records updated on or after this date are synced. Example: `"2024-01-01T00:00:00Z"` |

### Optional Config Keys

| Key | Type | Default | Description |
|---|---|---|---|
| `sandbox` | string | `"false"` | Set to `"true"` to target the Invoiced sandbox environment. |

### Example `config.json`

```json
{
  "api_key": "your_invoiced_api_key",
  "start_date": "2024-01-01T00:00:00Z",
  "sandbox": "true"
}
```

---

## Installation

Requires **Python 3.12+**.

```bash
pip install tap-invoiced
```

Or install from source:

```bash
git clone https://github.com/singer-io/tap-invoiced.git
cd tap-invoiced
pip install -e .
```

---

## Usage

### Discovery mode

```bash
tap-invoiced --config config.json --discover > catalog.json
```

### Sync mode

```bash
tap-invoiced --config config.json --catalog catalog.json
```

### Sync with state (incremental)

```bash
tap-invoiced --config config.json --catalog catalog.json --state state.json
```

---

## Seeding sandbox test data

If some streams return `0` records in your sandbox account, you can create
minimal records for empty streams before running the tap:

```bash
python scripts/seed_sandbox_data.py --config config.json
```

The script checks these streams and only inserts records when a stream is
empty: `customers`, `plans`, `subscriptions`, `invoices`, `estimates`, and
`credit_notes`.

---

Copyright &copy; 2019 Stitch
