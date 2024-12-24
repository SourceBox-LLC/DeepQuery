import streamlit as st
import logging
import boto3
from botocore.exceptions import ClientError
from langchain_community.chat_message_histories import DynamoDBChatMessageHistory

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
# 1) Load AWS credentials and region from Streamlit secrets
# -------------------------------------------------------------------
ACCESS_KEY = st.secrets["default"]["ACCESS_KEY"]
SECRET_KEY = st.secrets["default"]["SECRET_KEY"]
REGION     = st.secrets["default"]["REGION"]

# -------------------------------------------------------------------
# 2) Create a custom Boto3 Session (with region)
# -------------------------------------------------------------------
session = boto3.Session(
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
    region_name=REGION
)

# -------------------------------------------------------------------
# 3) Use session.resource() for DynamoDB (Option 1)
# -------------------------------------------------------------------
def create_dynamodb_table():
    """Create the DynamoDB table if it doesn't exist."""
    dynamodb = session.resource("dynamodb")  # uses custom session
    try:
        table = dynamodb.create_table(
            TableName="SessionTable",
            KeySchema=[{"AttributeName": "SessionId", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "SessionId", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        table.meta.client.get_waiter("table_exists").wait(TableName="SessionTable")
        logger.info("DynamoDB table 'SessionTable' created successfully.")
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceInUseException':
            logger.info("DynamoDB table 'SessionTable' already exists.")
        else:
            logger.error(f"Unexpected error: {e}")
            raise

def get_chat_history(session_id: str):
    """
    Retrieve chat history for a given session ID using a custom DynamoDB client.
    We pass 'dynamodb_client=session.client("dynamodb")' so it uses the same session.
    """
    history = DynamoDBChatMessageHistory(
        table_name="SessionTable",
        session_id=session_id,
        dynamodb_client=session.client("dynamodb"),  # Custom session-based client
    )
    messages = [{"role": msg.type, "content": msg.content} for msg in history.messages]
    logger.info(f"Chat history for session '{session_id}': {messages}")
    return messages

def add_user_message(session_id: str, message_content: str):
    """Add a user message to the chat history."""
    history = DynamoDBChatMessageHistory(
        table_name="SessionTable",
        session_id=session_id,
        dynamodb_client=session.client("dynamodb"),
    )
    history.add_user_message(message_content)
    logger.info(f"Added user message to session '{session_id}': {message_content}")

def add_ai_message(session_id: str, message_content: str):
    """Add an AI message to the chat history."""
    history = DynamoDBChatMessageHistory(
        table_name="SessionTable",
        session_id=session_id,
        dynamodb_client=session.client("dynamodb"),
    )
    history.add_ai_message(message_content)
    logger.info(f"Added AI message to session '{session_id}': {message_content}")

def clear_chat_history(session_id: str):
    """Clear all chat history for a given session ID."""
    try:
        dynamodb = session.resource("dynamodb")  # Custom session
        table = dynamodb.Table("SessionTable")
        table.delete_item(Key={"SessionId": session_id})
        logger.info(f"Chat history cleared for session '{session_id}'.")
        return True
    except Exception as e:
        logger.error(f"Error clearing chat history for session '{session_id}': {e}")
        return False

# -------------------------------------------------------------------
# 4) Example usage (if run directly)
# -------------------------------------------------------------------
if __name__ == "__main__":
    # Create the DynamoDB table if needed
    create_dynamodb_table()

    # Define a test session ID
    session_id = "test_session"

    # Add a user message to the chat history
    user_message = "Hello AI, how are you?"
    add_user_message(session_id, user_message)

    # Add an AI message to the chat history
    ai_message = "I'm doing well, thank you! How can I assist you today?"
    add_ai_message(session_id, ai_message)

    # Retrieve and print the chat history
    chat_history = get_chat_history(session_id)
    print("Chat History:")
    for msg in chat_history:
        print(f"{msg['role']}: {msg['content']}")
