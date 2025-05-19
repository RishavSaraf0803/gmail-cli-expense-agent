# fincli.py
import os
import json
import typer # For the CLI
import pandas as pd # For data handling
from googleapiclient.discovery import build # Gmail API
from google_auth_oauthlib.flow import InstalledAppFlow # Gmail Auth
from google.auth.transport.requests import Request # Gmail Auth
import boto3 # AWS SDK for Bedrock

# --- Configuration ---
app = typer.Typer(help="A CLI agent to chat about your Gmail expenses using Amazon Bedrock.")
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly'] # Read-only access
TOKEN_PATH = 'token.json'
CREDENTIALS_PATH = 'credentials.json' # Sensitive: Add to .gitignore
DB_PATH = "transactions.csv"
BEDROCK_REGION = 'us-east-1' # Or your preferred region
BEDROCK_MODEL_ID = "anthropic.claude-v2-1" # Or claude-3-sonnet-20240229-v1_0, etc.

# --- Gmail Authentication ---
def gmail_auth():
    creds = None
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, 'r') as token:
            creds_data = json.load(token)
            # Simplified credential loading for brevity in blog
            # In a real app, you'd properly use google.oauth2.credentials.Credentials.from_authorized_user_info
            # For this example, we'll assume the structure is directly usable or re-auth if structure is wrong.
            # A more robust solution would check expiry and refresh.
            creds = json.loads(creds_data) if isinstance(creds_data, str) else creds_data # Handle if already dict or needs json.loads
            # A placeholder for actual credential object creation, adapt as per your token.json structure
            # from google.oauth2.credentials import Credentials
            # creds = Credentials.from_authorized_user_info(creds_data, SCOPES)

    if not creds or not creds.get('valid'): # Simplified validity check
        if creds and creds.get('expired') and creds.get('refresh_token'):
            # Placeholder for refresh logic
            typer.echo("Credentials expired. Please re-authenticate by deleting token.json and running fetch.")
            raise typer.Exit(code=1)
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds_obj = flow.run_local_server(port=0)
            # Save the credentials for the next run
            # Storing the full creds_obj.to_json() is more robust
            with open(TOKEN_PATH, 'w') as token:
                token.write(creds_obj.to_json())
            creds = json.loads(creds_obj.to_json()) # Use the JSON version for consistency if reloaded

    # This part is tricky without knowing the exact structure of your 'creds' after loading.
    # The 'build' function expects a google.oauth2.credentials.Credentials object.
    # The following is a conceptual fix, assuming 'creds' can be used to reconstruct it.
    # You might need to adjust based on how you're actually storing/retrieving the token.
    from google.oauth2.credentials import Credentials
    # If creds is from to_json(), it can be loaded like this:
    credentials_object = Credentials.from_authorized_user_info(info=creds, scopes=SCOPES)
    return build('gmail', 'v1', credentials=credentials_object)


# --- Email Fetching ---
def fetch_emails(max_emails: int = 20): # Add parameter for flexibility
    service = gmail_auth()
    # More specific query to fetch relevant emails
    query = 'subject:("transaction alert" OR "debited" OR "credited" OR "spent on" OR "payment received")'
    results = service.users().messages().list(userId='me', q=query, maxResults=max_emails).execute()
    messages = results.get('messages', [])
    
    email_details = []
    if not messages:
        typer.echo("No transaction-related emails found with the current query.")
        return []

    for msg_info in messages:
        msg = service.users().messages().get(userId='me', id=msg_info['id'], format='metadata', metadataHeaders=['subject', 'date']).execute()
        snippet = msg.get("snippet", "")
        subject = next((header['value'] for header in msg['payload']['headers'] if header['name'] == 'Subject'), "No Subject")
        date = next((header['value'] for header in msg['payload']['headers'] if header['name'] == 'Date'), "No Date")
        # Combine snippet and subject for better context to LLM
        email_details.append({"id": msg_info['id'], "text_content": f"Subject: {subject}\nDate: {date}\nSnippet: {snippet}"})
    return email_details

# --- Bedrock LLM Interaction ---
def ask_bedrock_claude(prompt_text: str, is_extraction: bool = True):
    client = boto3.client('bedrock-runtime', region_name=BEDROCK_REGION)
    
    # Tailor the prompt for either extraction or Q&A
    if is_extraction:
        # Refined extraction prompt
        system_prompt = """
You are an expert financial transaction extractor. From the provided email snippet, extract the following details:
- amount (float, the numerical value only)
- type (string, either "debit" or "credit")
- merchant (string, the name of the vendor or source of funds)
- date (string, in YYYY-MM-DD format. If only day/month, assume current year. Prioritize date from email content if available.)
- currency (string, e.g., "INR", "USD". Infer if not present, default to "INR")

If a detail is not clearly present, use "N/A".
Return ONLY a single valid JSON object with these keys.
"""
        final_prompt = f"{system_prompt}\n\nHuman: Here's the email content:\n{prompt_text}\n\nAssistant:"
    else: # For Q&A
        final_prompt = f"Human: {prompt_text}\n\nAssistant:"

    body = {
        "anthropic_version": "bedrock-2023-05-31", # Important for Claude 3
        "max_tokens": 1024, # Increased for potentially longer Q&A
        "messages": [
            {
                "role": "user",
                "content": [{"type": "text", "text": final_prompt}]
            }
        ]
    }
    if is_extraction and BEDROCK_MODEL_ID.startswith("anthropic.claude-3"):
         # Claude 3 specific system prompt placement
        body["system"] = system_prompt
        body["messages"] = [{"role": "user", "content": [{"type": "text", "text": f"Here's the email content:\n{prompt_text}"}]}]


    try:
        response = client.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body)
        )
        response_body = json.loads(response.get('body').read())
        
        if is_extraction:
            # For Claude 3, content is in response_body['content'][0]['text']
            # For Claude 2, it might be response_body['completion']
            raw_json_text = ""
            if BEDROCK_MODEL_ID.startswith("anthropic.claude-3"):
                 raw_json_text = response_body.get('content', [{}])[0].get('text', '{}')
            else: # Assuming Claude v2 or similar structure
                 raw_json_text = response_body.get('completion', '{}')

            # Clean the text to ensure it's valid JSON
            # Remove potential markdown ```json ... ```
            if raw_json_text.strip().startswith("```json"):
                raw_json_text = raw_json_text.strip()[7:-3].strip()
            elif raw_json_text.strip().startswith("```"):
                 raw_json_text = raw_json_text.strip()[3:-3].strip()


            return json.loads(raw_json_text)
        else:
            # For Q&A, return the text response
            if BEDROCK_MODEL_ID.startswith("anthropic.claude-3"):
                 return response_body.get('content', [{}])[0].get('text', "Sorry, I couldn't process that.")
            else: # Assuming Claude v2 or similar structure
                 return response_body.get('completion', "Sorry, I couldn't process that.")

    except Exception as e:
        typer.echo(f"Error communicating with Bedrock: {e}")
        if is_extraction:
            return {"amount": 0.0, "type": "N/A", "merchant": "Error Parsing", "date": "N/A", "currency": "N/A"}
        return "Sorry, there was an error processing your request with the AI."

# --- CLI Commands ---
@app.command()
def fetch(max_emails: int = typer.Option(20, "--max", "-m", help="Maximum number of emails to fetch.")):
    """Fetches transaction emails, extracts details using Bedrock, and saves to CSV."""
    typer.echo("Fetching emails and extracting transactions...")
    email_contents = fetch_emails(max_emails)
    if not email_contents:
        typer.echo("No emails fetched. Exiting.")
        return

    transactions = []
    with typer.progressbar(email_contents, label="Processing emails") as progress:
        for email_detail in progress:
            extracted_data = ask_bedrock_claude(email_detail["text_content"], is_extraction=True)
            # Basic validation
            if isinstance(extracted_data, dict) and extracted_data.get("merchant") != "Error Parsing":
                extracted_data['email_id'] = email_detail['id'] # Keep track of email
                transactions.append(extracted_data)
            else:
                typer.echo(f"\nSkipping one email due to parsing error or missing data: {extracted_data}")


    if not transactions:
        typer.echo("No transactions were successfully extracted.")
        return

    df = pd.DataFrame(transactions)
    # Ensure essential columns exist even if some extractions failed partially
    expected_cols = ["amount", "type", "merchant", "date", "currency", "email_id"]
    for col in expected_cols:
        if col not in df.columns:
            df[col] = "N/A" # Or appropriate default
    df = df[expected_cols] # Order columns


    if os.path.exists(DB_PATH):
        existing_df = pd.read_csv(DB_PATH)
        # Avoid duplicates based on email_id if it exists
        if 'email_id' in existing_df.columns and 'email_id' in df.columns:
            new_transactions_df = df[~df['email_id'].isin(existing_df['email_id'])]
        else:
            new_transactions_df = df # No way to deduplicate, append all

        combined_df = pd.concat([existing_df, new_transactions_df], ignore_index=True)
    else:
        combined_df = df
    
    combined_df.to_csv(DB_PATH, index=False)
    typer.echo(f"Saved/updated {len(df)} new transactions. Total in {DB_PATH}: {len(combined_df)}")

@app.command()
def summarize():
    """Provides a quick summary of your spending from the local CSV."""
    if not os.path.exists(DB_PATH):
        typer.echo(f"No transaction data found at {DB_PATH}. Run `python fincli.py fetch` first.")
        raise typer.Exit(code=1)
    
    df = pd.read_csv(DB_PATH)
    if df.empty:
        typer.echo("Transaction data is empty.")
        return

    # Ensure 'amount' is numeric, coercing errors to NaN then filling with 0
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
    
    total_spent = df[df["type"].str.lower() == "debit"]["amount"].sum()
    total_credited = df[df["type"].str.lower() == "credit"]["amount"].sum()
    
    typer.echo(f"--- Spending Summary ---")
    typer.echo(f"Total Spent: ₹{total_spent:,.2f}") # Added formatting
    typer.echo(f"Total Credited: ₹{total_credited:,.2f}") # Added formatting

    if not df[df["type"].str.lower() == "debit"].empty:
        top_merchant = df[df["type"].str.lower() == "debit"]["merchant"].mode()
        if not top_merchant.empty:
            typer.echo(f"Most Frequent Merchant (Debits): {top_merchant.values[0]}")
        else:
            typer.echo("No debit transactions to determine top merchant.")
    else:
        typer.echo("No debit transactions found.")

@app.command()
def chat():
    """Initiates a conversational Q&A session about your expenses."""
    if not os.path.exists(DB_PATH):
        typer.echo(f"No transaction data found. Run `python fincli.py fetch` first to build your knowledge base.")
        raise typer.Exit(code=1)

    df = pd.read_csv(DB_PATH)
    if df.empty:
        typer.echo("Transaction data is empty. Nothing to chat about yet!")
        return

    typer.echo("Welcome to FinCLI Chat! Ask me about your expenses (e.g., 'total spent on food?', 'list Zomato transactions'). Type 'exit' or 'quit' to end.")
    
    # Prepare a simplified context string for the LLM
    # Only include relevant fields and recent transactions to manage context window
    df_for_context = df.copy()
    # Convert date to datetime objects if not already, to sort
    df_for_context['date'] = pd.to_datetime(df_for_context['date'], errors='coerce')
    df_for_context = df_for_context.sort_values(by='date', ascending=False).head(50) # Limit context

    context_list = []
    for _, row in df_for_context.iterrows():
        date_str = row['date'].strftime('%Y-%m-%d') if pd.notnull(row['date']) else 'N/A'
        context_list.append(f"- {row['type']} of {row.get('currency','')} {row['amount']} for {row['merchant']} on {date_str}.")
    context_str = "\n".join(context_list)

    while True:
        question = typer.prompt("You > ")
        if question.lower() in ["exit", "quit"]:
            typer.echo("FinCLI > Goodbye!")
            break
        
        # Improved prompt for Bedrock Q&A
        # Note: For complex Q&A, you might need a more sophisticated RAG approach (Retrieval Augmented Generation)
        # This basic context stuffing is okay for simpler queries.
        prompt = f"""
You are FinCLI, a helpful personal finance assistant.
Based ONLY on the following transaction data, answer the user's question.
If the data doesn't contain the answer, say "I don't have that information in the current transaction data."
Do not make up information. Be concise.

Transaction Data:
{context_str}

User Question: {question}

Answer:
"""
        # Use the non-extraction mode for ask_bedrock_claude
        answer = ask_bedrock_claude(prompt, is_extraction=False) 
        typer.echo(f"FinCLI > {answer}")

if __name__ == "__main__":
    app()