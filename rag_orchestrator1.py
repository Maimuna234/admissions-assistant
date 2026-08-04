import os
import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

# Load your environment variables (assuming GOOGLE_API_KEY is in your .env)
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

# 1. Configure the Google GenAI SDK to use your specific API key
genai.configure(api_key=api_key)

# 2. Query Google's servers for all models available to your account
print("🔍 Searching for available Gemini models...")
available_models = []

# Loop through all models and filter for ones that support standard generation
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        # Google returns names as 'models/gemini-1.5-flash', so we strip the prefix
        model_name = m.name.replace("models/", "")
        available_models.append(model_name)
        print(f"  ✅ Found: {model_name}")

print("-" * 40)

# 3. Automatically select a valid model instead of guessing
if available_models:
    # Set a target preference, but fallback to the first available model if it's missing
    target_preference = "gemini-1.5-flash"
    
    if target_preference in available_models:
        selected_model = target_preference
    else:
        selected_model = available_models[0] # Grab the first active model on the list
        
    print(f"🚀 Initializing LangChain with verified model: [{selected_model}]")
    
    # 4. Pass the verified model string into your LangChain engine
    primary_llm = ChatGoogleGenerativeAI(
        model=selected_model, 
        temperature=0.0
    )
    print("✅ Primary LLM successfully initialized without 404 errors!")

else:
    print("❌ No valid models found. Please check your GOOGLE_API_KEY.")