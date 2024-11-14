# tap-invoiced

This is a [Singer](https://singer.io) tap that produces JSON-formatted data
following the [Singer
spec](https://github.com/singer-io/getting-started/blob/master/SPEC.md).

This tap:

- Pulls raw data from [Invoiced](https://invoiced.com)
- Extracts the following resources:
  - [Credit Notes](https://developer.invoiced.com/api/credit-notes#credit-note-object)
  - [Customers](https://developer.invoiced.com/api/customers#customer-object)
  - [Estimates](https://developer.invoiced.com/api/estimates#estimate-object)
  - [Invoices](https://developer.invoiced.com/api/invoices#invoice-object)
  - [Payments]((https://developer.invoiced.com/api/payments#payment-object))
  - [Plans](https://developer.invoiced.com/api/plans#plan-object)
  - [Subscriptions](https://developer.invoiced.com/api/subscriptions#subscription-object)
  - [Transactions](https://web.archive.org/web/20160904134609/http://invoiced.com/docs/api/#transactions) (deprecated)
- Outputs the schema for each resource
- Incrementally pulls data based on the input state

---

Copyright &copy; 2019 Stitch
