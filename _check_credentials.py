from dotenv import load_dotenv; load_dotenv('.env', override=True)
import os, requests

api_key = os.getenv('IBM_API_KEY')
print(f"API Key loaded: {api_key[:8]}...")

# Step 1: Get IAM token
token_resp = requests.post(
    'https://iam.cloud.ibm.com/identity/token',
    data={'grant_type': 'urn:ibm:params:oauth:grant-type:apikey', 'apikey': api_key},
    headers={'Content-Type': 'application/x-www-form-urlencoded'}
)
if token_resp.status_code != 200:
    print('IAM token error:', token_resp.text)
    exit(1)

token = token_resp.json()['access_token']
print('IAM token obtained: OK')

# Step 2: List Watsonx projects
proj_resp = requests.get(
    'https://api.dataplatform.cloud.ibm.com/v2/projects?limit=10',
    headers={'Authorization': 'Bearer ' + token}
)
print(f'Projects API status: {proj_resp.status_code}')
if proj_resp.status_code == 200:
    projects = proj_resp.json().get('resources', [])
    if projects:
        print(f'Found {len(projects)} project(s):')
        for p in projects:
            name = p['entity']['name']
            guid = p['metadata']['guid']
            print(f'  Name: {name}')
            print(f'  ID:   {guid}')
            print()
    else:
        print('No projects found under this API key.')
        print('You need to create a project at: https://dataplatform.cloud.ibm.com')
else:
    print('Error listing projects:', proj_resp.text[:400])
