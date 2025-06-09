import streamlit as st
import os
from dotenv import load_dotenv
from DroolsLLMAgent_updated import DroolsLLMAgent
from logger_utils import logger, log_operation

# Load environment variables
load_dotenv()


# Initialize the agent
@st.cache_resource
def get_agent():
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            st.error("OPENAI_API_KEY environment variable is not set")
            return None

        rules_dir = os.path.join(os.getcwd(), "rules")
        os.makedirs(rules_dir, exist_ok=True)

        agent = DroolsLLMAgent(api_key=api_key, rules_dir=rules_dir)
        logger.info("Agent initialized successfully")
        return agent
    except Exception as e:
        logger.error(f"Error initializing agent: {str(e)}")
        st.error(f"Error initializing agent: {str(e)}")
        return None


# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
    logger.info("Initialized new chat session")

# Set up the page
st.set_page_config(page_title="Drools Rule Assistant", page_icon="🤖", layout="wide")
st.title("🤖 Drools Rule Assistant")

# Get the agent
agent = get_agent()
if agent is None:
    st.error(
        "Failed to initialize the agent. Please check your environment variables and try again."
    )
    st.stop()

# Input box for new user message
user_input = st.chat_input("Type your message here...")
if user_input:
    logger.info(f"Received user input: {user_input[:100]}...")  # Log first 100 chars

    # Store user message
    st.session_state.messages.append({"role": "user", "content": user_input})

    # Handle user message with logging
    try:
        logger.debug("Processing user message...")
        response = agent.handle_user_message(user_input)

        # Log the operation
        log_operation(
            "chat_interaction",
            {
                "user_input": user_input,
                "response": response[:100],  # Log first 100 chars of response
            },
        )

    except Exception as e:
        error_msg = f"Error processing message: {str(e)}"
        logger.error(error_msg, exc_info=True)
        st.error(f"🔴 {error_msg}")
        log_operation("chat_interaction", {"user_input": user_input}, error=e)
        raise

    # Store assistant reply
    st.session_state.messages.append({"role": "assistant", "content": response})

# Display chat history
for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

# Reset conversation button
if st.button("🔄 Reset Conversation"):
    logger.info("Resetting conversation")
    st.session_state.messages = []
    log_operation("reset_conversation")
    st.experimental_rerun()
