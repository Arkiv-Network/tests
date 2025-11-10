## Explorer E2E Tests

This package contains Playwright end-to-end smoke tests for the Kaolin explorer at [https://explorer.kaolin.hoodi.arkiv.network/](https://explorer.kaolin.hoodi.arkiv.network/).

### Setup

```bash
cd /Users/krzysztoffonal/programming/golem/tests/e2e-explorer
bun install
bunx playwright install
```

### Running the tests

```bash
bun run test
```

- Override the target explorer by exporting `EXPLORER_BASE_URL`.
- Provide custom addresses by exporting `EXPLORER_ADDRESSES` as a comma-separated list.
- Derive addresses automatically by setting `EXPLORER_MNEMONIC` (with optional `EXPLORER_ADDRESS_COUNT`, default `3`).
- Use `bun run test:headed` for a headed run or `bun run codegen` to explore selectors.

Each test records interaction timings and attaches them to the Playwright report (`test-results` directory) for quick performance diagnostics.
