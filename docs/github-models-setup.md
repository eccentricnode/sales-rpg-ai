# GitHub Models Integration Guide

## Overview

GitHub Models provides **free AI inference** for prototyping and development. It's the perfect way to get started with Sales RPG AI without needing a credit card or complex setup.

## Why GitHub Models?

| Feature | GitHub Models | OpenRouter | Azure AI | LocalAI |
|---------|---------------|------------|----------|---------|
| **Cost** | ✅ Free | 🟡 Free tier + paid | 💰 Paid (with startup credits) | ✅ Free |
| **Setup** | ⚡ 2 minutes | ⚡ 5 minutes | 🔧 Complex | 🔧 Requires GPU |
| **Models** | GPT-4o, Llama 3.1, Phi-3 | 100+ models | GPT-4, proprietary | Local models only |
| **Rate Limits** | Generous for dev | Limited free tier | Pay-as-you-go | Unlimited |
| **Privacy** | Cloud-based | Cloud-based | Cloud-based | ✅ 100% local |
| **Migration** | → Easy to Azure | → Various | N/A | N/A |

**Best for:** Getting started quickly, prototyping, then migrating to Azure for production.

## Quick Start (5 Minutes)

### Step 1: Create GitHub Personal Access Token

1. Go to: **https://github.com/settings/tokens/new**
2. Give it a name: `Sales RPG AI - GitHub Models`
3. Set expiration: 90 days (or longer)
4. Enable scope: **`models:read`** ✓
5. Click **Generate token**
6. **Copy the token** (you won't see it again!)

   It looks like: `ghp_abcd1234efgh5678ijkl9012mnop3456qrst`

### Step 2: Configure Environment

Edit your `.env` file:

```bash
# Set provider to GitHub Models
LLM_PROVIDER=github

# Add your token
GITHUB_TOKEN=ghp_your_token_here

# Choose a model (optional, defaults to gpt-4o-mini)
GITHUB_MODEL=gpt-4o-mini
```

### Step 3: Run the Application

```bash
make up
```

That's it! Open **http://localhost:8080** and start using it.

## Available Models

GitHub Models provides access to several state-of-the-art models:

| Model | ID | Best For | Speed | Quality |
|-------|-----|----------|-------|---------|
| **GPT-4o mini** | `gpt-4o-mini` | Fast responses, low cost | ⚡⚡⚡ | ⭐⭐⭐ |
| **GPT-4o** | `gpt-4o` | High quality, complex reasoning | ⚡⚡ | ⭐⭐⭐⭐⭐ |
| **Llama 3.1 405B** | `meta-llama-3.1-405b-instruct` | Open source, very capable | ⚡ | ⭐⭐⭐⭐ |
| **Llama 3.1 70B** | `meta-llama-3.1-70b-instruct` | Balanced open source | ⚡⚡ | ⭐⭐⭐⭐ |
| **Phi-3.5** | `phi-3.5-mini-instruct` | Fast, efficient, Microsoft | ⚡⚡⚡ | ⭐⭐⭐ |
| **Mistral Large** | `mistral-large-2` | European AI, strong performance | ⚡⚡ | ⭐⭐⭐⭐ |

**Recommendation for Sales RPG AI:**
- **Development**: `gpt-4o-mini` (fast, cheap, good quality)
- **Production**: Migrate to Azure OpenAI with `gpt-4o`

## Rate Limits

GitHub Models has generous rate limits for development:

| Limit Type | Value |
|------------|-------|
| Requests per minute | ~15-60 (varies by model) |
| Requests per day | ~1,500 |
| Tokens per request | Model-dependent |
| Concurrent requests | 5 |

**For Sales RPG AI**, this is more than enough for:
- ✅ Real-time conversation analysis
- ✅ Testing with multiple sales calls per day
- ✅ Building and debugging features

If you hit limits, the app will automatically queue requests.

## Switching Providers

GitHub Models uses the **OpenAI-compatible API**, making it easy to switch providers:

### Switch to OpenRouter (more free models)

```bash
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-v1-your-key
OPENROUTER_MODEL=meta-llama/llama-3.3-70b-instruct:free
```

### Switch to Azure AI (production)

```bash
LLM_PROVIDER=azure
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4o
```

### Switch back to Local (privacy)

```bash
LLM_PROVIDER=local
LOCAL_AI_BASE_URL=http://localhost:8080/v1
LOCAL_AI_MODEL=phi-3.5-mini
```

**No code changes needed!** Just update `.env` and restart.

## Migration Path to Production

GitHub Models → Azure AI is seamless:

1. **Sign up for Microsoft for Startups**
   - Get $100K-$150K in Azure credits
   - Includes OpenAI access

2. **Create Azure OpenAI resource**
   - Deploy GPT-4o or GPT-4o-mini
   - Get endpoint and key

3. **Update `.env`**
   ```bash
   LLM_PROVIDER=azure
   AZURE_OPENAI_API_KEY=<from Azure portal>
   AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
   AZURE_OPENAI_DEPLOYMENT=gpt-4o
   ```

4. **Restart**
   ```bash
   make up
   ```

**Same code, better infrastructure.** Azure provides:
- ✅ 99.9% uptime SLA
- ✅ Enterprise security
- ✅ No rate limits (pay-as-you-go)
- ✅ Global deployment
- ✅ Compliance certifications

## Troubleshooting

### "No access to model" error

**Cause**: Token doesn't have `models:read` scope.

**Fix**:
1. Go to https://github.com/settings/tokens
2. Click on your token
3. Enable `models:read` scope
4. Save changes
5. Restart the app

### "Authentication failed" error

**Cause**: Token is invalid or expired.

**Fix**:
1. Create a new token at https://github.com/settings/tokens/new
2. Copy the new token
3. Update `GITHUB_TOKEN` in `.env`
4. Restart

### Rate limit errors

**Cause**: Exceeded free tier limits.

**Fix**:
- **Short term**: Wait a few minutes for limits to reset
- **Long term**: Switch to Azure AI for production

### Model not available

**Cause**: Model ID is incorrect.

**Fix**: Use exact model IDs from table above:
```bash
# ✅ Correct
GITHUB_MODEL=gpt-4o-mini

# ❌ Wrong
GITHUB_MODEL=gpt-4o-mini-2024
```

## FAQ

**Q: Is GitHub Models really free?**
A: Yes! It's designed for prototyping and development. No credit card required.

**Q: Can I use this in production?**
A: GitHub Models is intended for development. For production, migrate to Azure AI (same API, better infrastructure).

**Q: How do I get more capacity?**
A: Apply to [Microsoft for Startups](https://www.microsoft.com/en-us/startups) for $100K-$150K in Azure credits.

**Q: Which model should I use?**
A: `gpt-4o-mini` is the best balance of speed, cost, and quality for Sales RPG AI.

**Q: Can I switch back to OpenRouter or LocalAI?**
A: Yes! Just change `LLM_PROVIDER` in `.env`. No code changes needed.

**Q: Do I need to change my code to migrate to Azure?**
A: Nope! The API is identical. Just update environment variables.

## Resources

- **GitHub Models**: https://github.com/features/models
- **GitHub Models Docs**: https://docs.github.com/en/github-models
- **Create Token**: https://github.com/settings/tokens/new
- **Microsoft for Startups**: https://www.microsoft.com/en-us/startups
- **Azure OpenAI**: https://azure.microsoft.com/en-us/products/ai-services/openai-service

## Next Steps

1. ✅ Set up GitHub Models (this guide)
2. 📚 Read the main [README.md](../README.md)
3. 🚀 Build your sales AI features
4. 💰 Apply to Microsoft for Startups for Azure credits
5. 🏢 Migrate to Azure AI when ready for production

---

**Questions?** Check the main [README](../README.md) or [open an issue](https://github.com/yourusername/sales-rpg-ai/issues).
