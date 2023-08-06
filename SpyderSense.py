import os
import glob
import requests
import pandas as pd
import time
from bs4 import BeautifulSoup
from termcolor import colored

# Helper functions for printing
def print_green(text):
    print(colored(text, 'green'))

def print_red(text):
    print(colored(text, 'red'))

# Function to check internet connection
def internet_connection_check():
    try:
        response = requests.get("https://www.google.com/")
        return True
    except requests.ConnectionError:
        return False

# Global constant for the API key
api_key = "ZPFU35862MVWSNADAFAKMEZXWHUQZQZWYY"  # Replace with your actual Etherscan API Key

while True:
    # Display menu
    print("\nMenu:")
    print("1- Explore all files")
    print("2- Exit")
    choice = input("Select an option : ")

    # Based on choice, either get all Excel and CSV files or exit
    if choice == '1':
        files = glob.glob('./*.xlsx') + glob.glob('./*.csv')
    elif choice == '2':
        print("Exiting...")
        exit(0)
    else:
        print_red("Invalid choice!")
        continue

    # Check internet connection
    if not internet_connection_check():
        print_red("Error: No internet connection!")
        continue

    # Define cutoff time (11 days prior to the current time)
    cutoff_time = time.time() - 11*24*60*60

    # Iterate over each file and analyze
    for file in files:
        try:
            df = pd.read_excel(file) if file.endswith('.xlsx') else pd.read_csv(file)
        except Exception as e:
            print_red(f"Error reading file {file}: {e}")
            continue

        # Ensure 'address' column exists in the data
        if 'address' not in df.columns:
            continue

        # Process each address in the data file
        for address in df['address']:
            url = f"https://api.etherscan.io/api?module=account&action=tokentx&address={address}&startblock=0&endblock=999999999&sort=desc&apikey={api_key}"
            response = requests.get(url).json()

            tokens_data = {}
            unique_hashes = set()

            most_recent_tx = response['result'][0] if 'result' in response and len(response['result']) > 0 else None
            if most_recent_tx:
                most_recent_tx_time = int(most_recent_tx['timeStamp'])
                if most_recent_tx_time < cutoff_time:
                    print_red(f"The account {address} is not active.")
                    continue

            if response['status'] == '1' and response['result'] and int(response['result'][0]['timeStamp']) >= cutoff_time:
                print_green(f"The account {address} is active.")
                print_green(f"Processing transactions for address: {address}")

                for token_transfer in response['result']:
                    token_name = token_transfer['tokenName']
                    txn_hash = token_transfer['hash']

                    if txn_hash in unique_hashes:
                        continue

                    unique_hashes.add(txn_hash)
                    base_url = 'https://etherscan.io/tx/' + txn_hash
                    headers = {'User-Agent': 'Mozilla/5.0'}
                    txn_response = requests.get(base_url, headers=headers)

                    if txn_response.status_code == 200:
                        soup = BeautifulSoup(txn_response.content, 'html.parser')
                        spans_me_1 = soup.find_all('span', {'class': 'me-1'})

                        ether_values_in = 0
                        ether_values_out = 0
                        usd_values_in = 0
                        usd_values_out = 0

                        for i in range(len(spans_me_1)):
                            value = spans_me_1[i].get_text(strip=True)
                            if "($" in value:
                                usd_value = float(value.replace('$', '').replace('(', '').replace(')', '').replace(',', ''))
                                ether_value = float(spans_me_1[i - 1].get_text(strip=True).replace('Ether', '').replace(',', ''))


                                if address in token_transfer['to']:
                                    ether_values_in += ether_value
                                    usd_values_in += usd_value
                                else:
                                    ether_values_out += ether_value
                                    usd_values_out += usd_value

                        if token_name not in tokens_data:
                            tokens_data[token_name] = {
                                'total_in_ether_value': 0,
                                'total_out_ether_value': 0,
                                'total_in_usd_value': 0,
                                'total_out_usd_value': 0,
                                'count_in_transfers': 0,
                                'count_out_transfers': 0
                            }

                        tokens_data[token_name]['total_in_ether_value'] += ether_values_in
                        tokens_data[token_name]['total_out_ether_value'] += ether_values_out
                        tokens_data[token_name]['total_in_usd_value'] += usd_values_in
                        tokens_data[token_name]['total_out_usd_value'] += usd_values_out

                        if address in token_transfer['to']:
                            tokens_data[token_name]['count_in_transfers'] += 1
                        else:
                            tokens_data[token_name]['count_out_transfers'] += 1

                for token, data in tokens_data.items():
                    data['difference_ether'] = data['total_out_ether_value'] - data['total_in_ether_value'] if data['count_out_transfers'] > 0 else data['total_in_ether_value']
                    data['difference_usd'] = data['total_out_usd_value'] - data['total_in_usd_value'] if data['count_out_transfers'] > 0 else data['total_in_usd_value']

                    if data['total_out_ether_value'] == 0 and data['difference_ether'] > 0:
                        data['win/lose'] = '---'
                    elif data['difference_ether'] > 0:
                        data['win/lose'] = 1
                    elif data['difference_ether'] < 0:
                        data['win/lose'] = 0
                    else:
                        data['win/lose'] = '---'

                # Save results to Excel in the "ready_files" directory
                output_directory = "ready_files"
                if not os.path.exists(output_directory):
                    os.makedirs(output_directory)

                output_file_path = os.path.join(output_directory, f"{txn_hash}.xlsx")
                df_out = pd.DataFrame.from_dict(tokens_data, orient='index')
                df_out = df_out.reset_index()
                df_out = df_out.rename(columns={"index": "tokenName"})

                # Additional columns
                df_out['address hash'] = address
                df_out['tokens count'] = len(tokens_data)
                win_times = df_out[df_out['win/lose'] == 1].shape[0]
                df_out['win times'] = f"{win_times}/{len(tokens_data)}"

                # Rearrange the columns to put 'address hash' before 'tokenName'
                columns_order = ['address hash', 'tokenName', 'total_in_ether_value', 'total_out_ether_value', 'total_in_usd_value', 'total_out_usd_value', 'count_in_transfers', 'count_out_transfers', 'difference_ether', 'difference_usd', 'win/lose', 'tokens count', 'win times']
                df_out = df_out[columns_order]

                # Save to Excel
                output_directory = "ready_files"
                if not os.path.exists(output_directory):
                    os.makedirs(output_directory)
                output_file_path = os.path.join(output_directory, f"{address}.xlsx")
                df_out.to_excel(output_file_path, index=False)
                print_green(f"Data saved to {output_file_path}")
                df_out = df_out.reset_index()
                df_out = df_out.rename(columns={"index": "tokenName"})
                df_out.reset_index(drop=True, inplace=True)
                df_out.to_excel(output_file_path, index=False)

                print_green(f"Data saved to {output_file_path}")

                for token, data in tokens_data.items():
                    print(f"{txn_hash}, {token}")

                    # Display details for each token
                    print(f"\tTotal Ether In Value: {data['total_in_ether_value']:.4f}")
                    print(f"\tTotal Ether Out Value: {data['total_out_ether_value']:.4f}")
                    print(f"\tTotal USD In Value: ${data['total_in_usd_value']:.2f}")
                    print(f"\tTotal USD Out Value: ${data['total_out_usd_value']:.2f}")
                    print(f"\tDifference in Ether: {data['difference_ether']:.4f}")
                    print(f"\tDifference in USD: ${data['difference_usd']:.2f}")
                    win_lose_str = "WIN" if data['win/lose'] == 1 else "LOSE" if data['win/lose'] == 0 else "NO ACTIVITY"
                    print(f"\tStatus: {win_lose_str}")
                    print("-" * 50)  # prints a line separator

            else:
                print_red(f"Failed to fetch transactions for address: {address}. {response['message']}")

    print_green(f"Finished processing transactions for {file}")

    print_green("Processing completed for all files!")

# 0x2d108e77ede06f89a0f285b2acc40491fb886ab2 ZPFU35862MVWSNADAFAKMEZXWHUQZQZWYY