import { createWalletClient, http as httpTransport } from "@arkiv-network/sdk";
import { kaolin, mendoza } from "@arkiv-network/sdk/chains";
import { privateKeyToAccount } from "@arkiv-network/sdk/accounts";
import { ExpirationTime, jsonToPayload } from "@arkiv-network/sdk/utils";

// Load the private key from the environment file.
const privateKey = process.env.PRIVATE_KEY;
if (!privateKey) {
  throw new Error("PRIVATE_KEY is not set in the .env file.");
}

const network = process.env.NETWORK ?? "mendoza";
if (network !== "mendoza" && network !== "kaolin") {
  throw new Error(
    `Unsupported NETWORK: ${network}. Supported: mendoza, kaolin`
  );
}

const account = privateKeyToAccount(privateKey as `0x${string}`);

export const arkivClient = createWalletClient({
  chain: network === "mendoza" ? mendoza : kaolin,
  transport: httpTransport(),
  account,
});

/**
 * Create many entities in bulk. The payload do not matter for this test.
 */
export async function createManyEntities(numEntities: number) {
  const createPayloads = [];
  for (let i = 0; i < numEntities; i++) {
    createPayloads.push({
      payload: jsonToPayload({
        data: `Entity number ${i}`,
        timestamp: Date.now(),
      }),
      contentType: "application/json" as const,
      attributes: [{ key: "test_entity", value: `entity_${i}` }],
      expiresIn: ExpirationTime.fromHours(1),
    });
  }

  const result = await arkivClient.mutateEntities({
    creates: createPayloads,
  });

  return result;
}
