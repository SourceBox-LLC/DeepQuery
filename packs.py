import boto3
import json
import logging
import streamlit as st
import os
import requests

# Initialize a session using Boto3 for remaining Lambda functions
ACCESS_KEY = st.secrets["default"]["ACCESS_KEY"]
SECRET_KEY = st.secrets["default"]["SECRET_KEY"]
REGION = st.secrets["default"]["REGION"]

logging.info(f"Using AWS Region: {REGION}")

# Create a Boto3 session
session = boto3.Session(
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
    region_name=REGION
)

# API URL
API_URL = os.getenv('API_URL', 'http://localhost:5000')

# Create a Lambda client for pinecone queries
lambda_client = session.client('lambda')

# Function to fetch current packs
def get_current_packs():
    # Check if user is logged in and access token is available
    if not st.session_state.logged_in or not st.session_state.access_token:
        logging.warning("User not logged in or access token not available")
        return []
    
    logging.info(f"Getting packs for user: {st.session_state.get('username', 'Unknown')}")
    logging.info(f"Access token: {st.session_state.access_token[:10]}... (truncated)")
    
    try:
        # Make a request to the API to get user packs
        headers = {'Authorization': f'Bearer {st.session_state.access_token}'}
        logging.info(f"Making request to {API_URL}/user/packs")
        
        response = requests.get(f'{API_URL}/user/packs', headers=headers)
        logging.info(f"Pack API response status: {response.status_code}")
        
        if response.status_code == 200:
            packs = response.json()
            logging.info(f"Retrieved {len(packs)} packs")
            
            # Transform the data to match the expected format
            formatted_packs = []
            for pack in packs:
                formatted_packs.append({
                    'Pack Name': pack['pack_name'],
                    'Description': pack['description'],
                    'Date Created': pack['date_created'].split('T')[0] if 'T' in pack['date_created'] else pack['date_created'],
                    'Pack ID': pack['id']
                })
            return formatted_packs
        else:
            logging.error(f"Failed to fetch packs: {response.text}")
            return []
            
    except Exception as e:
        logging.error(f"Error fetching packs: {e}")
        return []


def query_pinecone_pack(username, pack_name, query):
    # Return None immediately if "No Pack" is selected
    if pack_name == "No Pack":
        return None
    
    # Define the payload for the Lambda function
    payload = {
        "body": {
            "action": "query_pack",
            "username": username,
            "pack_name": pack_name,
            "query": query
        }
    }

    try:
        # Invoke the Lambda function
        response = lambda_client.invoke(
            FunctionName='pinecone-embedding-HelloWorldFunction-tHPspSqIP5SE',
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        logging.info("Lambda function invoked successfully")

        # Read and parse the response
        response_payload = json.loads(response['Payload'].read())
        logging.info("Received response from Lambda: %s", response_payload)

        # Check for errors in the response
        if 'errorMessage' in response_payload:
            logging.error("Error in Lambda invocation: %s", response_payload['errorMessage'])
            return None

        return response_payload

    except Exception as e:
        logging.error("Error invoking Lambda function: %s", e)
        return None


if __name__ == "__main__":
    print(get_current_packs())

    print(query_pinecone_pack("newuser", "My Custom Pack", "who is elon musk?"))
