import os
import re
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from autogen import AssistantAgent, UserProxyAgent
from autogen.coding import (
    DockerCommandLineCodeExecutor,
    LocalCommandLineCodeExecutor,
)

# ============================================================
# LOAD ENVIRONMENT VARIABLES & SECRETS SAFELY
# ============================================================

load_dotenv()


def get_api_key():
    """Safely retrieves the API key checking Streamlit Secrets,

    then environment variables, returning an empty string if missing.
    """
    try:
        if "OPENAI_API_KEY" in st.secrets:
            return st.secrets["OPENAI_API_KEY"]
    except Exception:
        # Prevents StreamlitSecretNotFoundError when secrets.toml doesn't exist locally
        pass

    return os.getenv("OPENAI_API_KEY", "")


env_api_key = get_api_key()

# Detect if running on Streamlit Community Cloud
IS_STREAMLIT_CLOUD = (
    os.getenv("STREAMLIT_SERVER_GATHER_USAGE_STATS") is not None
    or "STREAMLIT_SHARING" in os.environ
)

# ============================================================
# STREAMLIT PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="AutoGen Code Execution Agent",
    page_icon="🤖",
    layout="wide",
)

st.title("🤖 AutoGen Python Code Execution Agent")

st.write(
    "Enter a Python coding task below. AutoGen will generate and execute the Python code."
)

# ============================================================
# SIDEBAR CONFIGURATION
# ============================================================

st.sidebar.header("⚙️ Configuration")

api_key = st.sidebar.text_input(
    "OpenRouter / API Key",
    value=env_api_key,
    type="password",
    help="Enter your OpenRouter or OpenAI API key.",
)

model_name = st.sidebar.selectbox(
    "LLM Model",
    [
        "openai/gpt-4o-mini",
        "openai/gpt-4o",
        "openai/gpt-4.1-mini",
    ],
)

# Handle Docker availability guardrail for Streamlit Cloud deployment
if IS_STREAMLIT_CLOUD:
    st.sidebar.warning(
        "⚠️ Docker unavailable on Streamlit Cloud. Defaulting to Local Execution."
    )
    executor_options = ["Local Execution"]
    default_idx = 0
else:
    executor_options = ["Local Execution", "Docker Execution"]
    default_idx = 0

executor_type = st.sidebar.radio(
    "Code Execution Environment",
    options=executor_options,
    index=default_idx,
    help=(
        "Local Execution runs Python directly on your machine. "
        "Docker Execution runs code inside an isolated Docker container."
    ),
)

# ============================================================
# WORKING DIRECTORY SETUP
# ============================================================

work_dir = Path("coding")
work_dir.mkdir(parents=True, exist_ok=True)

# ============================================================
# USER INPUT
# ============================================================

user_prompt = st.text_area(
    "📝 Enter your coding task",
    placeholder="Example: Write a Python program to calculate the sum of numbers from 1 to 100.",
    height=120,
)

# ============================================================
# RUN AGENT
# ============================================================

if st.button("🚀 Run Agent Task", type="primary"):

    if not api_key:
        st.error(
            "❌ API key not found. Please provide an API key in secrets, .env, or sidebar."
        )
        st.stop()

    if not user_prompt.strip():
        st.warning("⚠️ Please enter a coding task.")
        st.stop()

    # Instantiate Code Executor
    executor = None
    try:
        if executor_type == "Docker Execution":
            st.info("🐳 Initializing Docker Python executor...")
            executor = DockerCommandLineCodeExecutor(
                image="python:3-slim",
                timeout=60,
                work_dir=work_dir,
                auto_remove=True,
            )
        else:
            st.info("🐍 Initializing Local Python executor...")
            executor = LocalCommandLineCodeExecutor(
                timeout=60,
                work_dir=work_dir,
            )

    except Exception as e:
        st.error(f"❌ Executor initialization failed: {e}")
        st.exception(e)
        st.stop()

    # LLM Configuration
    llm_config = {
        "config_list": [
            {
                "model": model_name,
                "api_key": api_key,
                "base_url": "https://openrouter.ai/api/v1",
            }
        ],
        "temperature": 0,
    }

    # Setup Agents
    assistant = AssistantAgent(
        name="Code_Writer",
        llm_config=llm_config,
        system_message=(
            "You are an expert Python coding assistant.\n\n"
            "Follow these rules:\n"
            "1. Generate valid Python code.\n"
            "2. Put executable Python code inside a ```python``` markdown block.\n"
            "3. The code will be executed by the code executor.\n"
            "4. Do not say TERMINATE immediately after generating code.\n"
            "5. Wait for the execution result.\n"
            "6. If execution fails, analyze the error and fix the code.\n"
            "7. After successful execution, clearly report the final result.\n"
            "8. Only output TERMINATE after the task has been successfully completed and reported."
        ),
    )

    user_proxy = UserProxyAgent(
        name="Code_Executor_Proxy",
        llm_config=False,
        code_execution_config={
            "executor": executor,
        },
        human_input_mode="NEVER",
        max_consecutive_auto_reply=8,
        is_termination_msg=lambda message: (
            "TERMINATE" in message.get("content", "").strip()
        ),
    )

    # Safe execution sequence supporting both Local and Docker executors
    with st.spinner("🤖 Agent is generating and executing Python code..."):
        try:
            if hasattr(executor, "start"):
                executor.start()

            chat_res = user_proxy.initiate_chat(
                assistant,
                message=user_prompt,
            )
        except Exception as e:
            st.error(f"❌ Agent execution failed: {e}")
            st.exception(e)
            st.stop()
        finally:
            if hasattr(executor, "stop"):
                executor.stop()

    st.success("✅ Agent task completed!")

    # Parse chat output
    chat_history = chat_res.chat_history if hasattr(chat_res, "chat_history") else []

    generated_code = ""
    execution_output = ""

    for msg in chat_history:
        content = (
            msg.get("content", "")
            if isinstance(msg, dict)
            else getattr(msg, "content", "")
        )
        if not content:
            continue

        # Extract latest Python code block
        match = re.findall(
            r"```python\s*(.*?)```", content, re.DOTALL | re.IGNORECASE
        )
        if match:
            generated_code = match[-1].strip()

        # Extract execution result
        if "exitcode:" in content.lower():
            execution_output = content.strip()

    # Output Tabs
    tab1, tab2, tab3 = st.tabs([
        "💻 Generated Code",
        "▶️ Execution Result",
        "💬 Agent Conversation",
    ])

    with tab1:
        st.subheader("🐍 Python Code Generated by Agent")
        if generated_code:
            st.code(generated_code, language="python")
        else:
            st.info("No Python code block was detected.")

    with tab2:
        st.subheader("▶️ Python Execution Result")
        if execution_output:
            st.code(execution_output, language="text")
        else:
            st.warning("No separate execution result block was detected.")

    with tab3:
        st.subheader("💬 AutoGen Agent Conversation")
        for msg in chat_history:
            sender = (
                msg.get("name") or msg.get("role") or "Agent"
                if isinstance(msg, dict)
                else getattr(msg, "name", "Agent")
            )
            content = (
                msg.get("content", "")
                if isinstance(msg, dict)
                else getattr(msg, "content", "")
            )
            if not content:
                continue

            st.markdown(f"**🤖 {sender}**")
            if "```python" in content:
                match = re.search(
                    r"```python\s*(.*?)```", content, re.DOTALL | re.IGNORECASE
                )
                if match:
                    st.code(match.group(1).strip(), language="python")
                remaining_text = re.sub(
                    r"```python\s*.*?```",
                    "",
                    content,
                    flags=re.DOTALL | re.IGNORECASE,
                ).strip()
                if remaining_text:
                    st.write(remaining_text)
            else:
                st.write(content)

# ============================================================
# SIDEBAR FOOTER
# ============================================================

st.sidebar.markdown("---")
st.sidebar.info(
    "Environment: **"
    + ("Streamlit Cloud" if IS_STREAMLIT_CLOUD else "Local/Self-Hosted")
    + "**"
)