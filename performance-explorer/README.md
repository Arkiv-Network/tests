# performance-explorer

K6 performance tests for the Arkiv Explorer.

## Prerequisites

- [k6](https://k6.io/docs/get-started/installation/)
- [bun](https://bun.sh/)

## Setting up the environment

Install dependencies using bun:

```bash
bun install
```

Create a `.env` file with your private key:

```bash
PRIVATE_KEY=0x...
```

## Running the test

### Full test (setup + k6)

Creates entities and runs the k6 performance test:

```bash
bun run test
```

### Step-by-step

1. Create entities (saves keys to `entity-keys.json`):

```bash
bun run setup
# Or with custom count:
NUM_ENTITIES=1000 bun run setup
```

2. Run k6 performance test:

```bash
bun run test:k6
# Or directly with k6:
k6 run index.ts
```

## Configuration

Environment variables:

- `NUM_ENTITIES` - Number of entities to create (default: 500)
- `READ_REQUESTS_PER_ITERATION` - Requests per iteration in k6 (default: 3)
- `MAX_BLOCK_HEIGHT` - Maximum block height for random queries (default: 300,000)
