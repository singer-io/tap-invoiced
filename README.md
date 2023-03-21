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
  - [Transactions](https://invoiced.com/docs/api/#transaction-object)
- Outputs the schema for each resource
- Incrementally pulls data based on the input state

---

Copyright &copy; 2019 Stitch
