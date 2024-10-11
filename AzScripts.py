from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.resourcegraph import ResourceGraphClient
from azure.mgmt.monitor import MonitorManagementClient
import datetime

# Remplacez par votre ID de souscription Azure
subscription_id = 'votre_subscription_id'

# Initialisation des clients Azure
credential = DefaultAzureCredential()
resource_client = ResourceManagementClient(credential, subscription_id)
resource_graph_client = ResourceGraphClient(credential)
monitor_client = MonitorManagementClient(credential, subscription_id)

# Fonctionnalité 1 : Afficher toutes les ressources avec leur date de création, sauf celles dans les groupes spécifiés
def list_resources_excluding_groups(exclude_groups_file):
    # Lecture des groupes de ressources à exclure
    with open(exclude_groups_file, 'r') as f:
        excluded_resource_groups = [line.strip() for line in f if line.strip()]

    # Requête pour obtenir les ressources avec leur date de création
    query = '''
    Resources
    | where type != 'microsoft.resources/resourcegroups'
    | project name, resourceGroup, properties.creationTime, properties.createdTime, properties.timestamp
    '''
    query_options = {'subscriptions': [subscription_id]}
    result = resource_graph_client.resources(query=query, options=query_options)

    print("Ressources excluant les groupes spécifiés :")
    for item in result.data:
        if item['resourceGroup'] not in excluded_resource_groups:
            creation_date = item.get('properties.creationTime') or item.get('properties.createdTime') or item.get('properties.timestamp') or 'N/A'
            print(f"Nom de la ressource: {item['name']}, Date de création: {creation_date}")

# Fonctionnalité 2 : Afficher les ressources dans les groupes contenant un tag spécifique
def list_resources_in_tagged_groups(tag_name):
    tagged_groups = []
    for rg in resource_client.resource_groups.list():
        if rg.tags and tag_name in rg.tags:
            tagged_groups.append(rg.name)

    print(f"Ressources dans les groupes de ressources avec le tag '{tag_name}':")
    for rg_name in tagged_groups:
        resources = resource_client.resources.list_by_resource_group(rg_name)
        for res in resources:
            # La date de création peut ne pas être directement disponible
            print(f"Nom de la ressource: {res.name}, Date de création: N/A")

# Fonctionnalité 3 : Afficher les comptes de stockage avec le nombre de transactions des 10 derniers jours
def list_storage_accounts_transactions():
    storage_accounts = resource_client.resources.list(filter="resourceType eq 'Microsoft.Storage/storageAccounts'")
    end_time = datetime.datetime.utcnow()
    start_time = end_time - datetime.timedelta(days=10)
    interval = None  # Intervalle personnalisé

    print("Comptes de stockage avec le nombre de transactions des 10 derniers jours :")
    for sa in storage_accounts:
        metrics_data = monitor_client.metrics.list(
            sa.id,
            timespan="{}/{}".format(start_time.isoformat(), end_time.isoformat()),
            interval=interval,
            metricnames='Transaction',
            aggregation='Total'
        )
        total_transactions = 0
        for metric in metrics_data.value:
            for timeseries in metric.timeseries:
                for data in timeseries.data:
                    if data.total:
                        total_transactions += data.total
        print(f"Compte de stockage: {sa.name}, Transactions (10 derniers jours): {int(total_transactions)}")

# Exécution principale
if __name__ == "__main__":
    exclude_groups_file = 'exclude_resource_groups.txt'  # Nom du fichier texte contenant les groupes à exclure
    tag_name = 'notre_tag'  # Le tag à rechercher dans les groupes de ressources

    # Appel des fonctionnalités
    list_resources_excluding_groups(exclude_groups_file)
    print("\n")
    list_resources_in_tagged_groups(tag_name)
    print("\n")
    list_storage_accounts_transactions()
