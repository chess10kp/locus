# LLM Chat Launcher Setup Guide

The LLM Chat Launcher allows you to chat with various AI models directly from the locus launcher interface. It supports Gemini (default), OpenAI, Claude, and Grok.

## API Key Setup

You need to set up API keys for the LLM providers you want to use. The launcher supports two methods for storing API keys:

### Method 1: Environment Variables (Recommended)

Set the following environment variables in your shell profile (e.g., `~/.bashrc`, `~/.zshrc`, or `~/.profile`):

```bash
# Gemini (Google AI)
export GEMINI_API_KEY="your_gemini_api_key_here"

# OpenAI
export OPENAI_API_KEY="your_openai_api_key_here"

# Anthropic Claude
export ANTHROPIC_API_KEY="your_anthropic_api_key_here"

# xAI Grok
export GROK_API_KEY="your_grok_api_key_here"
```

After setting the environment variables, restart your shell or run `source ~/.bashrc` (or your profile file).

### Method 2: Configuration File

Alternatively, create a configuration file at `~/.config/locus/llm_config.json`:

```json
{
  "api_keys": {
    "GEMINI_API_KEY": "your_gemini_api_key_here",
    "OPENAI_API_KEY": "your_openai_api_key_here",
    "ANTHROPIC_API_KEY": "your_anthropic_api_key_here",
    "GROK_API_KEY": "your_grok_api_key_here"
  }
}
```

**Note**: Environment variables take precedence over the config file. Use the config file only if you cannot set environment variables.

## Getting API Keys

### Gemini (Google AI)
1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with your Google account
3. Create a new API key
4. Copy the API key and set it as `GEMINI_API_KEY`

### OpenAI
1. Go to [OpenAI API Keys](https://platform.openai.com/api-keys)
2. Sign in to your OpenAI account
3. Create a new API key
4. Copy the API key and set it as `OPENAI_API_KEY`

### Anthropic Claude
1. Go to [Anthropic Console](https://console.anthropic.com/)
2. Sign in to your Anthropic account
3. Navigate to API Keys section
4. Create a new API key
5. Copy the API key and set it as `ANTHROPIC_API_KEY`

### xAI Grok
1. Go to [xAI Console](https://console.x.ai/)
2. Sign in to your xAI account
3. Navigate to API Keys section
4. Create a new API key
5. Copy the API key and set it as `GROK_API_KEY`

## Usage

Once you've set up your API keys, you can use the LLM chat launcher:

### Starting a Chat
- Type `>ai` in the launcher to open the chat interface
- The launcher will resize to a larger window (1000x700) for better chat experience
- Start typing your message and press Enter

### Provider Commands
- `>ai provider:openai` - Switch to OpenAI GPT-4
- `>ai provider:claude` - Switch to Anthropic Claude
- `>ai provider:grok` - Switch to xAI Grok
- `>ai provider:gemini` - Switch back to Gemini (default)

### Chat Commands
While in chat mode, you can use these commands:
- `>ai clear` - Clear chat history
- `>ai copy` - Copy the last response to clipboard
- `>ai regenerate` or `>ai regen` - Regenerate the last response

### Chat History
- Chat history is automatically saved and restored between sessions
- Located at `~/.cache/locus/llm_history.json`
- History persists across provider switches

## Default Models

The launcher uses these default models:
- **Gemini**: `gemini-2.0-flash`
- **OpenAI**: `gpt-4`
- **Claude**: `claude-3-sonnet-20240229`
- **Grok**: `grok-beta`

## Troubleshooting

### "No valid API key" Error
- Check that you've set the correct environment variable or config file entry
- Verify the API key is valid and hasn't expired
- Make sure the variable name matches exactly (case-sensitive)

### "API error" Messages
- Check your internet connection
- Verify the API key has sufficient credits/permissions
- Some providers may have rate limits or temporary outages

### Chat History Not Loading
- Check that `~/.cache/locus/llm_history.json` exists and is readable
- The file may be corrupted; you can safely delete it to start fresh

### Provider Not Available
- Make sure you have a valid API key for that provider
- Some providers may require additional setup or verification

## Security Notes

- API keys are sensitive credentials - never commit them to version control
- Environment variables are recommended over config files for better security
- The launcher only makes requests to official API endpoints
- Chat history is stored locally and not transmitted anywhere