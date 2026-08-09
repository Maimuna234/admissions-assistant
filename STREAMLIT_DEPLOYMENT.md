# Deploying to Streamlit Community Cloud

This repository now includes a Streamlit entrypoint at app.py so it can be deployed directly from GitHub to Streamlit Community Cloud.

## Requirements checklist

Before deploying, confirm the repository contains:
- app.py as the Streamlit entrypoint
- requirements.txt with the package list
- a GitHub repository with the project files committed
- a Gemini API key stored as a Streamlit secret named GEMINI_API_KEY

## Prepare the repository

1. Commit all files, including:
   - app.py
   - requirements.txt
   - rag_orchestrator.py
   - clearing_knowledge_base.json
   - admissions_structured.db
   - chroma_db/
   - .streamlit/secrets.toml (optional, local only)

2. Make sure the app can start without a local .env file. The app uses Streamlit secrets when available.

## Streamlit Community Cloud setup

1. Open Streamlit Community Cloud.
2. Click New app.
3. Choose the GitHub repository and branch.
4. Set the main file path to app.py.
5. Click Deploy.

## Required secrets

In Streamlit Cloud, add the secret:

```toml
[GEMINI_API_KEY]
value = "your-gemini-api-key"
```

Or use the Streamlit UI to create a secret named GEMINI_API_KEY with your API key.

## Notes

- The app expects the local SQLite database and Chroma index files to be present in the repository root.
- If the vector index is missing or the app cannot load it, the orchestrator will fall back to the local knowledge base and structured data paths.
- For best results, keep the repository data files tracked in Git or uploaded as part of the deployment.
