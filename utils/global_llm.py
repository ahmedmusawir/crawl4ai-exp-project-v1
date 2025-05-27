"""
Global LLM Registry/Factory for Stark Modular RAG Pipeline
----------------------------------------------------------
This module centralizes access to all supported LLMs across major vendors & local options.

- Each function returns a named LLM instance, ready for use.
- Plug-and-play model swapping: import and use whichever model you want.
- Handles API key detection, error management, and import laziness.
- Add new models with one function, no code duplication or lock-in.
"""

import os

def get_llm_gpt_4o_mini():
    """Returns GPT-4o (mini) LLM if OPENAI_API_KEY is set, else None."""
    try:
        from langchain_openai import ChatOpenAI
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            print("[WARN] No OPENAI_API_KEY found for GPT-4o.")
            return None
        return ChatOpenAI(model="gpt-4o", api_key=key, temperature=0.2)
    except Exception as e:
        print(f"[WARN] Failed to load OpenAI LLM: {e}")
        return None

def get_llm_claude_3_sonnet():
    """Returns Claude-3 Sonnet LLM if ANTHROPIC_API_KEY is set, else None."""
    try:
        from langchain_anthropic import ChatAnthropic
        key = os.getenv("ANTHROPIC_API_KEY")
        if not key:
            print("[WARN] No ANTHROPIC_API_KEY found for Claude-3.")
            return None
        return ChatAnthropic(model="claude-3-sonnet-20240229", api_key=key, temperature=0.2)
    except Exception as e:
        print(f"[WARN] Failed to load Anthropic LLM: {e}")
        return None

def get_llm_gemini_pro():
    """Returns Gemini Pro LLM if GOOGLE_API_KEY is set, else None."""
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        key = os.getenv("GOOGLE_API_KEY")
        if not key:
            print("[WARN] No GOOGLE_API_KEY found for Gemini.")
            return None
        return ChatGoogleGenerativeAI(model="gemini-pro", api_key=key, temperature=0.2)
    except Exception as e:
        print(f"[WARN] Failed to load Google Gemini LLM: {e}")
        return None

def get_llm_groq_llama3():
    """Returns Groq Llama-3 LLM if GROQ_API_KEY is set, else None."""
    try:
        from langchain_groq import ChatGroq
        key = os.getenv("GROQ_API_KEY")
        if not key:
            print("[WARN] No GROQ_API_KEY found for Groq Llama-3.")
            return None
        return ChatGroq(model="llama3-8b-8192", api_key=key, temperature=0.2)
    except Exception as e:
        print(f"[WARN] Failed to load Groq LLM: {e}")
        return None

def get_llm_ollama_phi3():
    """Returns Ollama Phi-3 local LLM (assumes Ollama is running locally), else None."""
    try:
        from langchain_community.chat_models.ollama import ChatOllama
        # No API key needed for local Ollama
        return ChatOllama(model="phi3")
    except Exception as e:
        print(f"[WARN] Failed to load Ollama LLM: {e}")
        return None

# Example of easily adding more models:
def get_llm_gpt_3_5_turbo():
    """Returns OpenAI GPT-3.5 Turbo if available."""
    try:
        from langchain_openai import ChatOpenAI
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            print("[WARN] No OPENAI_API_KEY found for GPT-3.5 Turbo.")
            return None
        return ChatOpenAI(model="gpt-3.5-turbo", api_key=key, temperature=0.2)
    except Exception as e:
        print(f"[WARN] Failed to load GPT-3.5 Turbo: {e}")
        return None

def available_llms():
    """Returns a dict of all available (non-None) LLMs with their friendly names."""
    registry = {
        "gpt_4o_mini": get_llm_gpt_4o_mini(),
        "claude_3_sonnet": get_llm_claude_3_sonnet(),
        "gemini_pro": get_llm_gemini_pro(),
        "groq_llama3": get_llm_groq_llama3(),
        "ollama_phi3": get_llm_ollama_phi3(),
        "gpt_3_5_turbo": get_llm_gpt_3_5_turbo(),
    }
    # Return only those with non-None values
    return {k: v for k, v in registry.items() if v is not None}

if __name__ == "__main__":
    print("[INFO] Available LLMs:")
    for name, llm in available_llms().items():
        print(f"  - {name}: {type(llm).__name__}")
