# Mistral AI Research Agent

This agent uses the Mistral AI API to research mistakes in tech professions and general job mistakes.

## Prerequisites

- Python 3.8+
- A Mistral AI API Key (Get one at [console.mistral.ai](https://console.mistral.ai/))

## Setup

1.  **Clone the repository** (if you haven't already).

2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure API Key**:
    - Create a file named `.env` in this directory.
    - Copy the content from `.env.example` into `.env`.
    - Replace `your_api_key_here` with your actual Mistral API Key.

    Example `.env` file:
    ```
    MISTRAL_API_KEY=your_actual_api_key_starts_with_...
    ```

## Usage

Run the agent script:

```bash
python research_agent.py
```

The agent will connect to Mistral AI using the `mistral-medium-latest` model and print a detailed report on tech profession and job mistakes.

## Troubleshooting

-   **Authentication Error**: Ensure your API key is correct in the `.env` file.
-   **Model Not Found**: If you receive an error about the model, you might not have access to `mistral-medium-latest`. Open `research_agent.py` and change `model = "mistral-medium-latest"` to `model = "mistral-small-latest"` or another available model.
