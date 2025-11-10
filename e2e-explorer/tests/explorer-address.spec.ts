import { expect, test } from "@playwright/test"
import { deriveAddressesFromMnemonic } from "./utils"

test.describe("Explorer address journeys", () => {
  test("should navigate to the address page and explore operations there", async ({ page }) => {
    const addresses = deriveAddressesFromMnemonic(
      process.env.EXPLORER_MNEMONIC ?? "",
      Number(process.env.EXPLORER_ADDRESS_COUNT ?? 3),
    )

    for (const address of addresses) {
      await page.goto("/")
      // find search input field
      const searchInput = page
        .getByPlaceholder("Search by query / address / entity key / txn hash / block... ")
        .first()
      await searchInput.click()
      await searchInput.fill(address.address)
      await searchInput.press("Enter")
      await page.waitForLoadState("networkidle")

      // click the found address in the list
      const addressItem = page.locator(`a[href="/address/${address.address}"]`)
      await addressItem.click()
      await page.waitForLoadState("networkidle")
      await expect(page).toHaveURL(new RegExp(`/address/${address.address}`))
    }
  })
})
