import os
import sys
from config.settings import get_settings
from db.init_db import create_and_seed_database
from main import handle_query


def main():
    print("=" * 60)
    print("      DATAVOX - LangGraph SQL AI Assistant Demo")
    print("=" * 60)

    # 1. Check & Seed Local SQLite Database
    print("\n[1/2] Verifying SQLite database...")
    create_and_seed_database()

    # 2. Check LLM Configuration
    settings = get_settings()
    api_key = settings.active_api_key

    print("\n[2/2] Checking LLM Configuration...")
    if not api_key or "your-" in api_key:
        print(f"  (!) Notice: No valid API key detected in .env for provider '{settings.llm_provider}'.")
        print("  Please configure GEMINI_API_KEY in .env.\n")
        return

    print(f"  (✓) {settings.llm_provider.upper()} API Key detected (Model: {settings.active_model}).")
    print("\nInteractive Chat Ready! Type your question or 'exit' to quit.\n")

    session_id = None
    while True:
        try:
            query = input("User > ").strip()
            if not query:
                continue
            if query.lower() in ("exit", "quit", "q"):
                print("Exiting Datavox Assistant. Goodbye!")
                break

            print("\nDatavox is processing your query through LangGraph...\n")
            response = handle_query(query, session_id=session_id)
            print(f"Datavox > {response}\n")
            print("-" * 60)

        except KeyboardInterrupt:
            print("\nSession interrupted. Goodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}\n")


if __name__ == "__main__":
    main()
