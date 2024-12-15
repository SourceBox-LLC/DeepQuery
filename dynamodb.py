from langchain_community.chat_message_histories import DynamoDBChatMessageHistory
import boto3
from botocore.exceptions import ClientError
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_dynamodb_table():
    """Create the DynamoDB table if it doesn't exist."""
    dynamodb = boto3.resource("dynamodb")
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

def get_chat_history(session_id):
    """Retrieve chat history for a given session ID."""
    history = DynamoDBChatMessageHistory(table_name="SessionTable", session_id=session_id)
    messages = [{"role": message.type, "content": message.content} for message in history.messages]
    logging.info(f"Chat history for session {session_id}: {messages}")
    return messages

def add_user_message(session_id, message_content):
    """Add a user message to the chat history."""
    history = DynamoDBChatMessageHistory(table_name="SessionTable", session_id=session_id)
    history.add_user_message(message_content)
    logging.info(f"Added user message to session {session_id}: {message_content}")

def add_ai_message(session_id, message_content):
    """Add an AI message to the chat history."""
    history = DynamoDBChatMessageHistory(table_name="SessionTable", session_id=session_id)
    history.add_ai_message(message_content)
    logging.info(f"Added AI message to session {session_id}: {message_content}")



if __name__ == "__main__":
    # Create the DynamoDB table
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
    for message in chat_history:
        print(f"{message['role']}: {message['content']}")
