import requests
import csv
from datetime import datetime, timedelta
from collections import defaultdict

api_token = 'your_api_token'
org_name = 'your_org_name'
# For TFCB use: https://app.terraform.io/api/v2
api_base_url = 'your_api_base_url' 

headers = {
    'Authorization': f'Bearer {api_token}',
    'Content-Type': 'application/vnd.api+json'
}

def get_workspace_names():
    url = f'{api_base_url}/organizations/{org_name}/workspaces'
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        workspaces = response.json()['data']
        return [(ws['attributes']['name'], ws['id']) for ws in workspaces]
    else:
        print(f'Error fetching workspaces: {response.status_code}')
        return []

def get_past_13_months():
    months = []
    today = datetime.now()
    for i in range(13):
        month = today - timedelta(days=30 * i)
        months.append(month.strftime('%Y-%m'))
    return months

def categorize_by_month(data, months):
    categorized = defaultdict(int)
    for item in data:
        item_date = datetime.strptime(item['attributes']['created-at'], '%Y-%m-%dT%H:%M:%S.%fZ')
        item_month = item_date.strftime('%Y-%m')
        if item_month in months:
            categorized[item_month] += 1
    return categorized

past_13_months = get_past_13_months()

def get_categorized_applies(workspace_id):
    url = f'{api_base_url}/workspaces/{workspace_id}/runs'
    applies = []
    while url:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            runs = data['data']
            applies.extend(run for run in runs if run['attributes']['status'] in ['applied', 'applying'])
            url = data['links']['next'] if 'next' in data['links'] else None
        else:
            print(f'Error fetching runs for workspace {workspace_id}: {response.status_code}')
            return None
    return categorize_by_month(applies, past_13_months)

def get_workspace_resources(workspace_id):
    url = f'{api_base_url}/workspaces/{workspace_id}/resources'
    unique_resource_ids = set()
    while url:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            resources = data['data']
            for resource in resources:
                if resource['type'] == 'resources':
                    unique_resource_ids.add(resource['id'])
            url = data['links']['next'] if 'next' in data['links'] else None
        else:
            print(f'Error fetching workspace resources: {response.status_code}')
            return None
    return len(unique_resource_ids)

def write_to_csv(workspaces_data, total_resources, total_applies_per_month):
    with open('terraform_metrics.csv', mode='w', newline='') as file:
        writer = csv.writer(file)
        header = ['Workspace Name', 'Resource Count'] + [f'{month} Applies' for month in past_13_months]
        writer.writerow(header)
        for workspace in workspaces_data:
            row = [workspace['name'], workspace['resource_count']] + [workspace['applies'][month] for month in past_13_months]
            writer.writerow(row)
        total_row = ['Total', total_resources] + [total_applies_per_month[month] for month in past_13_months]
        writer.writerow(total_row)

total_resources = 0
total_applies_per_month = defaultdict(int)
workspaces_data = []

workspace_names_ids = get_workspace_names()

for workspace_name, workspace_id in workspace_names_ids:
    resources_count = get_workspace_resources(workspace_id)
    total_resources += resources_count

    applies_by_month = get_categorized_applies(workspace_id)
    for month in past_13_months:
        total_applies_per_month[month] += applies_by_month.get(month, 0)

    workspaces_data.append({
        'name': workspace_name,
        'resource_count': resources_count,
        'applies': applies_by_month
    })

for data in workspaces_data:
    print(f'Workspace: {data["name"]}, Total Resources: {data["resource_count"]}')
    for month in past_13_months:
        print(f'  {month}: Applies: {data["applies"].get(month, 0)}')

print(f'\nTotal Resources across all workspaces: {total_resources}')
print('Total Applies per Month across all workspaces:')
for month in past_13_months:
    print(f'  {month}: {total_applies_per_month[month]}')

write_to_csv(workspaces_data, total_resources, total_applies_per_month)
