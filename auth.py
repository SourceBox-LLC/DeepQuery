import streamlit as st
import boto3
import json
import logging

# --- 1) ENSURE SECRETS ARE LOADED ---
# Debug line (optional): 
# st.write("Secrets loaded from st.secrets:", st.secrets)

# --- 2) INITIALIZE BOTO3 SESSION & CLIENT ---
# Read AWS creds from secrets
ACCESS_KEY = st.secrets["default"]["ACCESS_KEY"]
SECRET_KEY = st.secrets["default"]["SECRET_KEY"]
REGION = "us-east-1"

# Create a Boto3 session
session = boto3.Session(
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
    region_name=REGION
)

lambda_client = session.client('lambda')

# --- 3) DEFINE LOGIN PAGE ---
def login_page():
    st.title("Login Page")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit_button = st.form_submit_button("Login")

    if submit_button:
        logging.info("Login attempt for user: %s", username)

        # Define the payload for the Lambda function
        payload = {
            "action": "LOGIN_USER",
            "data": {
                "username": username,
                "password": password
            }
        }

        # Invoke the Lambda function
        try:
            response = lambda_client.invoke(
                FunctionName='sb-user-auth-sbUserAuthFunction-3StRr85VyfEC',  # <-- Replace with your Lambda name
                InvocationType='RequestResponse',
                Payload=json.dumps(payload)
            )
            logging.info("Lambda function invoked successfully.")
        except Exception as e:
            logging.error("Error invoking Lambda function: %s", e)
            st.error("An error occurred while processing your request.")
            return

        # Read the response
        response_payload = json.loads(response['Payload'].read())
        logging.info("Received response from Lambda: %s", response_payload)

        # Check the response and update session state
        if response_payload.get('statusCode') == 200:
            st.session_state.logged_in = True
            st.session_state.access_token = json.loads(response_payload['body'])['token']
            logging.info("User %s logged in successfully.", username)
            st.success("Logged in successfully!")
            st.rerun()
        else:
            logging.warning("Invalid login attempt for user: %s", username)
            st.error("Invalid username or password")

# --- 4) DEFINE LOGOUT ---
def logout():
    logging.info("User logged out.")
    st.session_state.logged_in = False
    st.session_state.access_token = None
    st.session_state.logout_trigger = not st.session_state.logout_trigger  # Toggle the trigger

# --- 5) GET USER INFO ---
def get_user_info(access_token):
    payload = {
        "action": "GET_USER",
        "token": access_token
    }
    try:
        response = lambda_client.invoke(
            FunctionName='sb-user-auth-sbUserAuthFunction-3StRr85VyfEC',  # <-- Replace with your Lambda name
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        logging.info("Lambda function invoked successfully for getting user info.")
    except Exception as e:
        logging.error("Error invoking Lambda function for getting user info: %s", e)
        return None

    # Read the response
    response_payload = json.loads(response['Payload'].read())
    logging.info("Received response from Lambda for getting user info: %s", response_payload)

    # Extract and return the user info from the response
    if response_payload.get('statusCode') == 200:
        user_info = json.loads(response_payload['body'])
        logging.info("User info retrieved successfully: %s", user_info)
        return user_info
    else:
        logging.warning("Failed to retrieve user info.")
        return None
