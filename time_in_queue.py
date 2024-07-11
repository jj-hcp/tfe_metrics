import requests
from datetime import datetime
import logging
from statistics import mean
import sys
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

#Update the org name and be sure to set the env variable TERRAFORM_TOKEN with your TF API Key
################################
TERRAFORM_ORG = "YOUR_ORG_NAME"
################################


API_BASE_URL = "https://app.terraform.io/api/v2"
TERRAFORM_TOKEN = os.environ.get('TERRAFORM_TOKEN')
if not TERRAFORM_TOKEN:
    raise ValueError("TERRAFORM_TOKEN environment variable is not set")

headers = {
    "Authorization": f"Bearer {TERRAFORM_TOKEN}",
    "Content-Type": "application/vnd.api+json"
}

def get_paginated_results(url):
    results = []
    while url:
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            results.extend(data['data'])
            url = data['links'].get('next')
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching data from {url}: {e}")
            raise
    return results

def get_workspaces():
    url = f"{API_BASE_URL}/organizations/{TERRAFORM_ORG}/workspaces"
    return get_paginated_results(url)

def get_runs(workspace_id):
    url = f"{API_BASE_URL}/workspaces/{workspace_id}/runs"
    return get_paginated_results(url)

def was_run_queued(run):
    status = run['attributes'].get('status')
    timestamps = run['attributes'].get('status-timestamps', {})
    return (status not in ['pending', 'fetching', 'fetching_completed'] and
            'queuing' in timestamps and 'planning' in timestamps)

def calculate_queue_time(run):
    if not was_run_queued(run):
        return 0

    timestamps = run['attributes']['status-timestamps']
    queuing_time = datetime.fromisoformat(timestamps['queuing'].rstrip('Z'))
    planning_time = datetime.fromisoformat(timestamps['planning'].rstrip('Z'))
    return (planning_time - queuing_time).total_seconds()

def analyze_workspaces():
    workspaces = get_workspaces()
    all_queue_times = []
    workspace_stats = {}

    for workspace in workspaces:
        workspace_id = workspace['id']
        workspace_name = workspace['attributes']['name']
        logging.info(f"Analyzing workspace: {workspace_name}")

        try:
            runs = get_runs(workspace_id)
            queued_runs = [run for run in runs if was_run_queued(run)]
            queue_times = [calculate_queue_time(run) for run in queued_runs]
            
            workspace_stats[workspace_name] = {
                "total_runs": len(runs),
                "queued_runs": len(queued_runs),
                "avg_queue_time": mean(queue_times) if queue_times else 0
            }
            
            all_queue_times.extend(queue_times)
        except Exception as e:
            logging.error(f"Error processing workspace {workspace_name}: {e}")

    overall_avg_queue_time = mean(all_queue_times) if all_queue_times else 0
    return workspace_stats, overall_avg_queue_time

def main():
    workspace_stats, overall_avg_queue_time = analyze_workspaces()

    print("Workspace Statistics:")
    for workspace, stats in workspace_stats.items():
        print(f"\n{workspace}:")
        print(f"  Total runs: {stats['total_runs']}")
        print(f"  Queued runs: {stats['queued_runs']}")
        print(f"  Average queue time: {stats['avg_queue_time']:.2f} seconds")

    print(f"\nOverall average queue time: {overall_avg_queue_time:.2f} seconds")

if __name__ == "__main__":
    main()
