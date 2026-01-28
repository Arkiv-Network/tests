import requests
import json

# Using the URL from your working curl command
NODE_URL = "http://oplimit.hoodi.arkiv.network/rpc"

def get_mempool_contents():
    # 1. We spoof the headers to look exactly like your working curl command
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'curl/7.68.0',  # <--- TRICK: Pretend to be curl
        'Accept': '*/*',
        'Connection': 'keep-alive'
    }

    payload = {
        "jsonrpc": "2.0",
        "method": "txpool_content",
        "params": [],
        "id": 1
    }

    print(f"Connecting to {NODE_URL}...")

    try:
        # requests.post automatically handles redirects (like curl -L)
        response = requests.post(NODE_URL, headers=headers, data=json.dumps(payload))
        response.raise_for_status()

        data = response.json()

        if 'error' in data:
            print(f"RPC Error: {data['error']['message']}")
            return

        result = data['result']
        pending = result.get('pending', {})
        queued = result.get('queued', {})

        # Calculate total counts (nested dictionaries: Address -> Nonce -> Tx)
        pending_count = sum(len(txs) for txs in pending.values())
        queued_count = sum(len(txs) for txs in queued.values())

        print("\n" + "=" * 40)
        print(f"MEMPOOL CONTENT (Success!)")
        print("=" * 40)
        print(f"Total Pending (Executable): {pending_count}")
        print(f"Total Queued  (Stuck)     : {queued_count}")
        print("-" * 40)

        # Optional: Inspect the first pending transaction found
        if pending_count > 0:
            first_addr = next(iter(pending))
            first_nonce = next(iter(pending[first_addr]))
            tx = pending[first_addr][first_nonce]

            print(f"Sample Tx from: {first_addr}")
            print(f"  Nonce: {first_nonce}")
            print(f"  Gas Price: {int(tx.get('gasPrice', '0'), 16) / 10**9} Gwei")
            # Some nodes return 'input', others 'data'
            input_data = tx.get('input', tx.get('data', '0x'))
            print(f"  Input Data: {input_data[:50]}...")

    except requests.exceptions.HTTPError as err:
        print(f"HTTP Error: {err}")
        # Print the response text to see why the server blocked it
        print(f"Server Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    get_mempool_contents()