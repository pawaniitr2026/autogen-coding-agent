import os
import re
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

#from autogen import AssistantAgent, UserProxyAgent
#from autogen.coding import (
#    DockerCommandLineCodeExecutor,
#    LocalCommandLineCodeExecutor,
#)


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()


# ============================================================
# STREAMLIT CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="AutoGen Code Execution Agent",
    page_icon="🤖",
    layout="wide",
)

st.title("🤖 AutoGen Python Code Execution Agent")

st.write(
    "Enter a Python coding task below. "
    "AutoGen will generate and execute the Python code."
)


# ============================================================
# API KEY
# ============================================================

env_api_key = os.getenv("OPENAI_API_KEY", "")

st.sidebar.header("⚙️ Configuration")

api_key = st.sidebar.text_input(
    "OpenRouter API Key",
    value=env_api_key,
    type="password",
    help="Enter your OpenRouter API key.",
)


# ============================================================
# MODEL SELECTION
# ============================================================

model_name = st.sidebar.selectbox(
    "LLM Model",
    [
        "openai/gpt-4o-mini",
        "openai/gpt-4o",
        "openai/gpt-4.1-mini",
    ],
)


# ============================================================
# CODE EXECUTOR SELECTION
# ============================================================

executor_type = st.sidebar.radio(
    "Code Execution Environment",
    [
        "Local Execution",
        "Docker Execution",
    ],
    help=(
        "Local Execution runs Python directly on your machine. "
        "Docker Execution runs code inside a Docker container."
    ),
)


# ============================================================
# WORKING DIRECTORY
# ============================================================

work_dir = Path("coding")
work_dir.mkdir(exist_ok=True)


# ============================================================
# USER INPUT
# ============================================================

user_prompt = st.text_area(
    "📝 Enter your coding task",
    placeholder=(
        "Example: Write a Python program to calculate "
        "the sum of numbers from 1 to 100."
    ),
    height=120,
)


# ============================================================
# RUN AGENT
# ============================================================

if st.button("🚀 Run Agent Task", type="primary"):

    # --------------------------------------------------------
    # Validate API Key
    # --------------------------------------------------------

    if not api_key:

        st.error(
            "❌ API key not found. "
            "Please add OPENAI_API_KEY to your .env file "
            "or enter the key in the sidebar."
        )

        st.stop()

    # --------------------------------------------------------
    # Validate User Prompt
    # --------------------------------------------------------

    if not user_prompt.strip():

        st.warning(
            "⚠️ Please enter a coding task."
        )

        st.stop()

    # --------------------------------------------------------
    # Create Code Executor
    # --------------------------------------------------------


try:
    if executor_type == "Docker Execution":
        st.info("🐳 Initializing Docker Python executor...")
        try:
            import docker
            from autogen.coding import DockerCommandLineCodeExecutor

            executor = DockerCommandLineCodeExecutor(
                image="python:3-slim",
                timeout=60,
                work_dir=work_dir,
                auto_remove=True,
            )
        except (ImportError, Exception) as docker_err:
            st.warning(
                "⚠️ Docker environment is not available on Streamlit Cloud. "
                "Falling back to Local Execution."
            )
            executor = LocalCommandLineCodeExecutor(
                timeout=60,
                work_dir=work_dir,
            )
    else:
        st.info("🐍 Initializing local Python executor...")
        executor = LocalCommandLineCodeExecutor(
            timeout=60,
            work_dir=work_dir,
        )
except Exception as e:
    st.error(f"❌ Executor initialization failed: {e}")
    st.exception(e)
    st.stop()

    # ========================================================
    # LLM CONFIGURATION
    # ========================================================

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

    # ========================================================
    # ASSISTANT AGENT
    # ========================================================

    assistant = AssistantAgent(
        name="Code_Writer",
        llm_config=llm_config,
        system_message=(
            "You are an expert Python coding assistant.\n\n"
            "Your job is to solve the user's programming task.\n\n"
            "Follow these rules:\n"
            "1. Generate valid Python code.\n"
            "2. Put executable Python code inside a "
            "```python``` markdown block.\n"
            "3. The code will be executed by the code executor.\n"
            "4. Do not say TERMINATE immediately after generating code.\n"
            "5. Wait for the execution result.\n"
            "6. If execution fails, analyze the error and fix the code.\n"
            "7. After successful execution, clearly report the final result.\n"
            "8. Only output TERMINATE after the task has been successfully "
            "completed and the result has been reported."
        ),
    )

    # ========================================================
    # USER PROXY / CODE EXECUTOR AGENT
    # ========================================================

    user_proxy = UserProxyAgent(
        name="Code_Executor_Proxy",
        llm_config=False,
        code_execution_config={
            "executor": executor,
        },
        human_input_mode="NEVER",
        max_consecutive_auto_reply=8,
        is_termination_msg=lambda message: (
            message.get("content", "")
            .strip()
            .endswith("TERMINATE")
        ),
    )

    # ========================================================
    # START AGENT CONVERSATION
    # ========================================================

    with st.spinner(
        "🤖 Agent is generating and executing Python code..."
    ):

        try:

            chat_res = user_proxy.initiate_chat(
                assistant,
                message=user_prompt,
            )

        except Exception as e:

            st.error(
                f"❌ Agent execution failed: {e}"
            )

            st.exception(e)
            st.stop()

    # ========================================================
    # TASK COMPLETED
    # ========================================================

    st.success(
        "✅ Agent task completed!"
    )

    # ========================================================
    # EXTRACT CHAT HISTORY
    # ========================================================

    chat_history = chat_res.chat_history

    # ========================================================
    # EXTRACT GENERATED PYTHON CODE
    # ========================================================

    generated_code = ""

    for msg in chat_history:

        if isinstance(msg, dict):

            content = msg.get(
                "content",
                "",
            )

        else:

            content = getattr(
                msg,
                "content",
                "",
            )

        if not content:
            continue

        # Search for Python markdown block
        match = re.search(
            r"```python\s*(.*?)```",
            content,
            re.DOTALL | re.IGNORECASE,
        )

        if match:

            generated_code = match.group(1).strip()

    # ========================================================
    # EXTRACT EXECUTION OUTPUT
    # ========================================================

    execution_output = ""

    for msg in chat_history:

        if isinstance(msg, dict):

            content = msg.get(
                "content",
                "",
            )

        else:

            content = getattr(
                msg,
                "content",
                "",
            )

        if not content:
            continue

        # AutoGen execution response usually contains
        # exitcode and execution output.
        if "exitcode:" in content.lower():

            execution_output = content.strip()

    # ========================================================
    # DISPLAY RESULTS IN TABS
    # ========================================================

    tab1, tab2, tab3 = st.tabs(
        [
            "💻 Generated Code",
            "▶️ Execution Result",
            "💬 Agent Conversation",
        ]
    )

    # ========================================================
    # TAB 1 - GENERATED CODE
    # ========================================================

    with tab1:

        st.subheader(
            "🐍 Python Code Generated by Agent"
        )

        if generated_code:

            st.code(
                generated_code,
                language="python",
            )

        else:

            st.info(
                "No Python code block was detected."
            )

    # ========================================================
    # TAB 2 - EXECUTION RESULT
    # ========================================================

    with tab2:

        st.subheader(
            "▶️ Python Execution Result"
        )

        if execution_output:

            st.code(
                execution_output,
                language="text",
            )

        else:

            st.warning(
                "No separate execution result was found "
                "in the AutoGen chat history."
            )

            st.info(
                "Check the Agent Conversation tab for "
                "the complete AutoGen response."
            )

    # ========================================================
    # TAB 3 - AGENT CONVERSATION
    # ========================================================

    with tab3:

        st.subheader(
            "💬 AutoGen Agent Conversation"
        )

        for msg in chat_history:

            if isinstance(msg, dict):

                sender = (
                    msg.get("name")
                    or msg.get("sender")
                    or msg.get("role")
                    or "Agent"
                )

                content = msg.get(
                    "content",
                    "",
                )

            else:

                sender = (
                    getattr(
                        msg,
                        "name",
                        None,
                    )
                    or getattr(
                        msg,
                        "role",
                        None,
                    )
                    or "Agent"
                )

                content = getattr(
                    msg,
                    "content",
                    "",
                )

            if not content:
                continue

            st.markdown(
                f"### 🤖 {sender}"
            )

            # Display Python code nicely
            if "```python" in content:

                match = re.search(
                    r"```python\s*(.*?)```",
                    content,
                    re.DOTALL | re.IGNORECASE,
                )

                if match:

                    st.code(
                        match.group(1).strip(),
                        language="python",
                    )

                # Display text outside code block
                remaining_text = re.sub(
                    r"```python\s*.*?```",
                    "",
                    content,
                    flags=re.DOTALL | re.IGNORECASE,
                ).strip()

                if remaining_text:

                    st.write(
                        remaining_text
                    )

            else:

                st.write(
                    content
                )


# ============================================================
# SIDEBAR INFORMATION
# ============================================================

st.sidebar.markdown("---")

st.sidebar.info(
    """
    **Agent Architecture**

    User
      ↓
    Streamlit
      ↓
    UserProxyAgent
      ↓
    Code_Writer Agent
      ↓
    Python Code
      ↓
    Code Executor
      ↓
    Execution Result
      ↓
    Code_Writer
      ↓
    Final Answer
    """
)