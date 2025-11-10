import { mnemonicToAccount } from "@arkiv-network/sdk/accounts"

export function deriveAddressesFromMnemonic(
  mnemonic: string,
  count: number,
  options?: {
    account?: number
    change?: number
  },
) {
  if (!mnemonic.trim()) {
    throw new Error("Mnemonic must be a non-empty string")
  }

  if (!Number.isFinite(count) || count <= 0) {
    throw new Error("Count must be a positive number")
  }

  const { account = 0, change = 0 } = options ?? {}

  return Array.from({ length: count }, (_, index) => {
    const derivationPath = `m/44'/60'/${account}'/${change}/${index + 1}` as const
    const accountData = mnemonicToAccount(mnemonic, { path: derivationPath })
    return {
      address: accountData.address,
      derivationPath,
    }
  })
}
