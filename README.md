# 🤖 AutoGen Code Execution Agent

An AI-powered Python Code Execution Agent built using:

- Python
- Streamlit
- Microsoft AutoGen
- OpenRouter
- Docker
- LLMs

## Architecture

User
↓
Streamlit UI
↓
AutoGen UserProxyAgent
↓
Code Writer Agent
↓
Python Code
↓
Docker Python Executor
↓
Execution Result
↓
Streamlit UI

## Features

- Generate Python code using an LLM
- Execute generated Python code
- Docker-based code execution
- Local Python execution
- Streamlit user interface
- Agent conversation history
- Generated code download
- OpenRouter LLM integration

## Installation

Clone the repository:

```bash
git clone https://github.com/YOUR_USERNAME/autogen-code-execution-agent.git
