import boto3
import json

# Initialize a session using Boto3
session = boto3.Session(
    aws_access_key_id='AKIA4MTWIIWUMKVY3KOL',
    aws_secret_access_key='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',
    region_name='us-east-1'
)

# Create a Lambda client
lambda_client = session.client('lambda')

# Define the payload for the Lambda function
payload = {
    "action": "LOGOUT_USER",
    "token": "the users access token"
}

# Invoke the Lambda function
response = lambda_client.invoke(
    FunctionName='sb-user-auth-sbUserAuthFunction-3StRr85VyfEC',  # Replace with your Lambda function name
    InvocationType='RequestResponse',  # Use 'Event' for asynchronous invocation
    Payload=json.dumps(payload)
)

# Read the response
response_payload = json.loads(response['Payload'].read())

# Print the response
print(response_payload)