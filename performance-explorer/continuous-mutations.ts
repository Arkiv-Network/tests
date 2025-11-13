import { ExpirationTime, jsonToPayload } from "@arkiv-network/sdk/utils";
import { arkivClient } from "./arkiv-client";

const ENTITIES_PER_ROUND = 1000;

let previousRoundEntityKeys: string[] = [];
let roundNumber = 0;

async function runRound() {
  roundNumber++;
  console.log(`\n--- Round ${roundNumber} ---`);

  try {
    // Create new entities
    const createPayloads = [];
    for (let i = 0; i < ENTITIES_PER_ROUND; i++) {
      createPayloads.push({
        payload: jsonToPayload({
          data: `Entity from round ${roundNumber}, index ${i}`,
          timestamp: Date.now(),
          roundNumber,
        }),
        contentType: "application/json" as const,
        attributes: [
          { key: "round", value: `${roundNumber}` },
          { key: "index", value: `${i}` },
        ],
        expiresIn: ExpirationTime.fromMinutes(1),
      });
    }

    const startCreate = Date.now();
    const { createdEntities, txHash: createTxHash } =
      await arkivClient.mutateEntities({
        creates: createPayloads,
      });
    const createDuration = Date.now() - startCreate;

    console.log(
      `✓ Created ${createdEntities.length} entities in ${createDuration}ms (tx: ${createTxHash})`
    );

    // Update random entities from the previous round
    if (previousRoundEntityKeys.length > 0) {
      const numToUpdate = Math.floor(
        Math.random() * previousRoundEntityKeys.length
      );
      const entitiesToUpdate = [];

      for (let i = 0; i < numToUpdate; i++) {
        const randomIndex = Math.floor(
          Math.random() * previousRoundEntityKeys.length
        );
        const entityKey = previousRoundEntityKeys[randomIndex];

        if (!entityKey) continue;

        entitiesToUpdate.push({
          entityKey: entityKey as `0x${string}`,
          payload: jsonToPayload({
            data: `Updated in round ${roundNumber}`,
            updatedAt: Date.now(),
            originalRound: roundNumber - 1,
          }),
          contentType: "application/json" as const,
          attributes: [
            { key: "updated_in_round", value: `${roundNumber}` },
            { key: "update_count", value: `${i}` },
          ],
          expiresIn: ExpirationTime.fromMinutes(1),
        });
      }

      if (entitiesToUpdate.length > 0) {
        const startUpdate = Date.now();
        const { updatedEntities, txHash: updateTxHash } =
          await arkivClient.mutateEntities({
            updates: entitiesToUpdate,
          });
        const updateDuration = Date.now() - startUpdate;

        console.log(
          `✓ Updated ${updatedEntities.length} entities from previous round in ${updateDuration}ms (tx: ${updateTxHash})`
        );
      }
    } else {
      console.log("⊘ No entities from previous round to update");
    }

    // Store this round's entities for the next round
    previousRoundEntityKeys = createdEntities;
  } catch (error) {
    console.error(`✗ Error in round ${roundNumber}:`, error);
  }
}

async function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function main() {
  console.log("Starting continuous entity mutations...");
  console.log(`- Creating ${ENTITIES_PER_ROUND} entities`);
  console.log("- Updating random entities from previous round");
  console.log("\nPress Ctrl+C to stop\n");

  while (true) {
    await runRound();
  }
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});
