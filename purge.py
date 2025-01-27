import threading
import time
from datetime import datetime, timedelta
from azure.identity import ClientSecretCredential
from azure.storage.blob import BlobServiceClient
from collections import defaultdict
import logging
from prettytable import PrettyTable

# Configuration variables
creation_days_to_delete = 30  # Number of days to determine old containers
timeout_minutes = 3  # Timeout for logging in minutes
spn_tenant_id = "your-tenant-id"
spn_client_id = "your-client-id"
spn_client_secret = "your-client-secret"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Function to delete containers older than a specified number of days in a storage account
def clean_old_containers(storage_account_name, storage_account_url, delete_map, status_map):
    try:
        # Authenticate with SPN credentials
        credential = ClientSecretCredential(
            tenant_id=spn_tenant_id, client_id=spn_client_id, client_secret=spn_client_secret
        )
        blob_service_client = BlobServiceClient(account_url=storage_account_url, credential=credential)
        containers_deleted = 0
        now = datetime.utcnow()
        cutoff_date = now - timedelta(days=creation_days_to_delete)

        # List and delete containers older than the specified number of days
        for container in blob_service_client.list_containers():
            creation_time = container.metadata.get("creation-time")
            if creation_time:
                container_date = datetime.strptime(creation_time, "%Y-%m-%dT%H:%M:%SZ")
                if container_date < cutoff_date:
                    blob_service_client.delete_container(container.name)
                    containers_deleted += 1

        # Update the maps
        delete_map[storage_account_name] = containers_deleted
        status_map[storage_account_name] = "Completed"

    except Exception as e:
        logger.error(f"Error processing storage account {storage_account_name}: {e}")
        delete_map[storage_account_name] = f"Error: {e}"
        status_map[storage_account_name] = "Error"

# Function to log the deletion map and thread status
def log_status(delete_map, status_map):
    table = PrettyTable()
    table.field_names = ["Storage Account", "Containers Deleted", "Status"]
    for account, status in status_map.items():
        containers_deleted = delete_map.get(account, "N/A")
        table.add_row([account, containers_deleted, status])
    logger.info(f"\n{table}")

# Main function to start jobs and log results
def main(storage_accounts):
    delete_map = defaultdict(int)
    status_map = {account["name"]: "Running" for account in storage_accounts}
    threads = []

    # Start a thread for each storage account
    for account in storage_accounts:
        storage_account_name = account["name"]
        storage_account_url = account["url"]
        thread = threading.Thread(
            target=clean_old_containers,
            args=(storage_account_name, storage_account_url, delete_map, status_map),
        )
        threads.append(thread)
        thread.start()

    # Log the map and status every timeout_minutes
    try:
        while any(thread.is_alive() for thread in threads):
            log_status(delete_map, status_map)
            time.sleep(timeout_minutes * 60)
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")

    # Wait for all threads to finish
    for thread in threads:
        thread.join()

    # Final log
    log_status(delete_map, status_map)

if __name__ == "__main__":
    # Input: List of storage accounts with their URLs
    storage_accounts = [
        {"name": "storage_account_1", "url": "https://storage_account_1.blob.core.windows.net/"},
        {"name": "storage_account_2", "url": "https://storage_account_2.blob.core.windows.net/"},
    ]

    main(storage_accounts)