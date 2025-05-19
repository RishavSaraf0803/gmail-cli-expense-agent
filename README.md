# FinCLI: Your Conversational Gmail Expense Tracker

FinCLI is a Python-based Command Line Interface (CLI) agent that securely connects to your Gmail account, extracts transaction information from your emails using Amazon Bedrock (Anthropic Claude), and allows you to conversationally query your expenses directly from your terminal.

Stop sifting through emails or complicated apps – just chat with your cash!

![FinCLI Demo Placeholder](https://via.placeholder.com/700x300.png?text=Imagine+a+GIF+of+FinCLI+in+Action+Here)
*(Ideally, replace the placeholder above with a GIF or screenshot of FinCLI in action)*

## ✨ Features

* **Secure Gmail Integration:** Uses Google's official API with read-only access to fetch transaction-related emails.
* **Intelligent Expense Extraction:** Leverages Amazon Bedrock (Claude LLM) to accurately parse transaction details (amount, merchant, date, type) from unstructured email snippets.
* **Local Data Storage:** Stores all extracted financial data in a simple, human-readable CSV file (`transactions.csv`) on your local machine. You own and control your data.
* **Conversational Interface:** Ask questions about your spending in natural language (e.g., "How much did I spend on food last week?").
* **Quick Summaries:** Get a fast overview of your total spending and top merchants.
* **Easy to Setup & Use:** Designed for a straightforward setup for those comfortable with CLI tools and cloud service basics.

## 🛠️ Tech Stack

* **Python 3.8+**
* **Gmail API:** For fetching emails.
* **Amazon Bedrock (Anthropic Claude):** For Large Language Model (LLM) based data extraction and Q&A.
* **Typer:** For building the user-friendly CLI.
* **Pandas:** For data manipulation and CSV handling.
* **Boto3:** AWS SDK for Python, to interact with Bedrock.
* **Google Auth Libraries:** For Gmail API authentication.

## 📋 Prerequisites

1.  **Python:** Ensure you have Python 3.8 or newer installed.
2.  **Google Cloud Account:**
    * A Google Cloud Project.
    * Gmail API enabled for your project.
    * OAuth 2.0 Client ID credentials (downloaded as `credentials.json`).
3.  **AWS Account:**
    * An AWS account.
    * Access to Amazon Bedrock in your chosen AWS region.
    * Model access granted for an Anthropic Claude model (e.g., Claude 3 Sonnet, Claude 3 Haiku, Claude 2.1) in Amazon Bedrock.
    * AWS CLI configured locally with credentials that have permissions to invoke Bedrock models.
4.  **Git (Optional):** If you plan to clone a repository.

## 🚀 Setup & Installation

1.  **Clone the Repository (Optional):**
    If this project is hosted on Git:
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```
    Otherwise, simply download `fincli.py` (and `requirements.txt` if provided) into a dedicated project directory.

2.  **Set up Google Cloud Credentials:**
    * Go to the [Google Cloud Console](https://console.cloud.google.com/).
    * Create a new project or select an existing one.
    * Navigate to "APIs & Services" > "Enabled APIs & services" and click "+ ENABLE APIS AND SERVICES". Search for "Gmail API" and enable it.
    * Navigate to "APIs & Services" > "Credentials".
    * Click "+ CREATE CREDENTIALS" > "OAuth client ID".
    * Select "Desktop app" for the Application type. Give it a name.
    * Click "CREATE". Download the JSON file and rename it to `credentials.json`.
    * **Important:** Place this `credentials.json` file in the same directory as your `fincli.py` script. **This file is sensitive and should NOT be committed to public repositories. Add it to your `.gitignore` file.**

3.  **Set up AWS & Amazon Bedrock:**
    * Ensure your AWS CLI is configured (run `aws configure` if you haven't already). Your AWS user/role needs permissions for `bedrock:InvokeModel`.
    * Log into the AWS Management Console, navigate to Amazon Bedrock.
    * Under "Model access" (usually at the bottom of the left navigation pane), request access for your desired Anthropic Claude model.
    * Note the **Model ID** (e.g., `anthropic.claude-3-sonnet-20240229-v1:0`) and the **AWS region** where you have model access. You might need to update these in the `fincli.py` script if they differ from the defaults.

4.  **Create a Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

5.  **Install Dependencies:**
    Create a `requirements.txt` file with the following content:
    ```txt
    typer[all]
    google-api-python-client
    google-auth-oauthlib
    google-auth-httplib2
    pandas
    boto3
    ```
    Then install them:
    ```bash
    pip install -r requirements.txt
    ```
    Alternatively, install manually:
    ```bash
    pip install "typer[all]" google-api-python-client google-auth-oauthlib google-auth-httplib2 pandas boto3
    ```

## ⚙️ Configuration (Inside `fincli.py`)

You may need to adjust the following constants at the top of `fincli.py` if your setup differs:

* `BEDROCK_REGION`: Set this to the AWS region where you have Bedrock model access (e.g., `'us-east-1'`, `'eu-central-1'`).
* `BEDROCK_MODEL_ID`: Set this to the specific Claude model ID you have access to and want to use (e.g., `"anthropic.claude-3-sonnet-20240229-v1:0"` or `"anthropic.claude-v2:1"`).

The script uses the following files which will be created/used in the same directory:
* `credentials.json`: (You provide this) For Gmail API authentication.
* `token.json`: Generated after successful Gmail authentication. You can delete this to re-authenticate.
* `transactions.csv`: Local database where extracted transaction data is stored.

## ▶️ Usage

All commands are run from your terminal in the directory containing `fincli.py`.

1.  **Fetch and Process Emails:**
    This is the first command you need to run. It will:
    * Authenticate with your Gmail account (a browser window will open for permission the first time).
    * Fetch emails matching transaction-related keywords.
    * Use Amazon Bedrock to extract transaction details.
    * Save the data to `transactions.csv`.

    ```bash
    python fincli.py fetch
    ```
    You can specify the maximum number of emails to fetch:
    ```bash
    python fincli.py fetch --max 50
    ```

2.  **Get a Spending Summary:**
    Displays total money spent, total credited, and your most frequent merchant (for debits).
    ```bash
    python fincli.py summarize
    ```

3.  **Chat About Your Expenses:**
    Initiates an interactive session where you can ask questions in natural language about the transactions stored in `transactions.csv`.
    ```bash
    python fincli.py chat
    ```
    Example questions:
    * `How much did I spend on Amazon this month?`
    * `What were my transactions last week?`
    * `List all credits.`
    * `What was my biggest expense in May?`

    Type `exit` or `quit` to end the chat session.

## 🔐 Security & Privacy

* **Read-Only Gmail Access:** The script requests `gmail.readonly` scope, meaning it can only read emails and cannot modify or send anything.
* **Local Data Storage:** All your transaction data extracted is stored locally in `transactions.csv`. It is not sent to any third-party server other than the necessary interaction with Amazon Bedrock for processing.
* **Sensitive Files:**
    * `credentials.json`: Contains your Google Cloud OAuth client secrets. **Keep this file secure and private. Do NOT commit it to version control if your repository is public.** Add it to your `.gitignore`.
    * `token.json`: Stores your OAuth token for Gmail access. While it can be refreshed, it's also best to keep this private.
* **AWS Credentials:** Handled by the AWS SDK (Boto3) typically via your shared AWS credentials file or IAM roles. Ensure these credentials have least-privilege permissions (only what's needed for Bedrock).

## 💡 Future Enhancements (Roadmap)

This tool is a great starting point! Here are some ideas for future development:

* **Automatic Categorization:** Use Bedrock to categorize expenses (e.g., food, utilities).
* **Budget Tracking:** Set and track monthly budgets per category.
* **Trend Analysis:** Compare spending across different periods.
* **Advanced Semantic Search:** Integrate vector databases (FAISS, ChromaDB) for more nuanced Q&A.
* **Support More Data Sources:** E.g., parsing bank statement PDFs.
* **GUI or Web Interface:** For users less comfortable with CLIs.

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! Please feel free to:
* Open an issue to discuss a bug or feature idea.
* Submit a pull request with your improvements.

*(If you are not planning to accept contributions, you can remove this section or state that.)*

## 📄 License

This project is licensed under the MIT License. See the `LICENSE` file for details.

*(Create a `LICENSE` file with the MIT License text if you choose this license.)*

---

**To make this README even better:**

* **Add a GIF/Screenshot:** Visuals make a huge difference. Tools like [Peek](https://github.com/phw/peek) (Linux) or [Kap](https://getkap.co/) (macOS) can help create simple GIFs of CLI interactions.
* **Create a `LICENSE` file:** If you include a license section, actually add the corresponding file.
* **Refine `BEDROCK_MODEL_ID`:** Ensure the default model ID in `fincli.py` and mentioned here is a widely available and suitable one (like Claude 3 Sonnet or Haiku, as they are often more cost-effective for such tasks than the full Opus or older Claude v2 models, depending on availability and performance needs).

This README provides a solid foundation for your project!