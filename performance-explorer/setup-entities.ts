import { createManyEntities } from "./arkiv-client";
import { writeFileSync } from "fs";

const NUM_ENTITIES = Number(process.env.NUM_ENTITIES ?? 500);

async function main() {
  console.log(`Creating ${NUM_ENTITIES} entities...`);

  const startTime = Date.now();
  const { createdEntities, txHash } = await createManyEntities(NUM_ENTITIES);
  const duration = Date.now() - startTime;

  console.log(
    `✓ Created ${createdEntities.length} entities in ${duration}ms (tx: ${txHash})`
  );

  // Save to file for k6 to load
  writeFileSync(
    "entity-keys.json",
    JSON.stringify(
      { entityKeys: createdEntities, createdAt: new Date().toISOString() },
      null,
      2
    )
  );

  console.log(`✓ Saved entity keys to entity-keys.json`);
}

main().catch((error) => {
  console.error("Failed to create entities:", error);
  process.exit(1);
});
