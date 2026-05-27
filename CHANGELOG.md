# Changelog

## 1.0.1
* Add per-stream access checks during discovery; streams returning HTTP 401 or 403 are excluded from the catalog with a warning instead of failing the entire discovery [#12](https://github.com/singer-io/tap-invoiced/pull/12)
* Added unit tests for `check_stream_access` helper, `_check_stream_access` wrapper, and access-gated `discover_streams()`

## 1.0.0
* Upgrade `singer-python` to `6.8.0` [#11](https://github.com/singer-io/tap-invoiced/pull/11)
