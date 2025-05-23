import os
from dotenv import load_dotenv
import streamlit as st
from DroolsLLMAgent import DroolsLLMAgent

# Load environment variables
print("Loading environment variables in RuleAgent_app.py...")
load_dotenv()

# Debug: Print environment status
print("OPENAI_API_KEY exists:", "Yes" if os.getenv("OPENAI_API_KEY") else "No")

# Initialize the Drools LLM Agent in session state
if 'agent' not in st.session_state:
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        st.error("Please set the OPENAI_API_KEY environment variable.")
        st.stop()
    print("Initializing DroolsLLMAgent with API key length:", len(openai_key))
    st.session_state.agent = DroolsLLMAgent(api_key=openai_key)

# Initialize chat history in session state
if 'messages' not in st.session_state:
    st.session_state.messages = []

st.title("🤖 Drools Rule Assistant")
st.markdown("Interact with the agent to add, search, edit or delete Drools rules.")

# Chat input
user_input = st.chat_input("Type your message here...")
if user_input:
    # Append user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    # Get assistant response
    assistant_reply = st.session_state.agent.handle_user_message(user_input)
    st.session_state.messages.append({"role": "assistant", "content": assistant_reply})

# Display chat history
for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.chat_message("user").write(msg["content"])
    else:
        st.chat_message("assistant").write(msg["content"])
