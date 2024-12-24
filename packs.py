import boto3
import json
import logging
import streamlit as st

# Initialize a session using Boto3
ACCESS_KEY = st.secrets["default"]["ACCESS_KEY"]
SECRET_KEY = st.secrets["default"]["SECRET_KEY"]
REGION = "us-east-1"

# Create a Boto3 session
session = boto3.Session(
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
    region_name=REGION
)

# Create a Lambda client
lambda_client = session.client('lambda')

# Function to fetch current packs
def get_current_packs():
    # Define the payload for the Lambda function
    payload = {
        "action": "LIST_USER_PACKS",
        "user_id": 2  # TODO: Replace with actual user_id from session
    }

    try:
        # Invoke the Lambda function
        response = lambda_client.invoke(
            FunctionName='sb-user-auth-sbUserAuthFunction-3StRr85VyfEC',
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        # Read and parse the response
        response_payload = json.loads(response['Payload'].read())
        
        if response_payload.get('statusCode') == 200:
            # Parse the body string into a dictionary
            body = json.loads(response_payload['body'])
            
            # Transform the data to match the expected format
            packs = []
            for pack in body['packs']:
                packs.append({
                    'Pack Name': pack['pack_name'],
                    'Description': pack['description'],
                    'Date Created': pack['date_created'].split('T')[0],
                    'Pack ID': pack['id']  # Add pack_id to the returned data
                })
            return packs
        else:
            logging.error("Failed to fetch packs: %s", response_payload)
            return []
            
    except Exception as e:
        logging.error("Error fetching packs: %s", e)
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
