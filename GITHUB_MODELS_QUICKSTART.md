# GitHub Models - Quick Start Guide

## TL;DR

GitHub Models is **FREE AI inference** that works perfectly with Sales RPG AI. Setup takes 2 minutes.

## Setup Steps

### 1. Get GitHub Personal Access Token

**Link**: https://github.com/settings/tokens/new

1. Token name: `Sales RPG AI`
2. Expiration: 90 days
3. ✓ Enable: `models:read`
4. Generate token
5. **Copy it!** (looks like `ghp_abc123...`)

### 2. Configure `.env`

```bash
cp .env.example .env
```

Edit `.env`:
```bash
LLM_PROVIDER=github
GITHUB_TOKEN=ghp_your_token_here
GITHUB_MODEL=gpt-4o-mini
```

### 3. Test It

```bash
python test_providers.py
```

You should see:
```
✅ SUCCESS! Provider is working correctly.
```

### 4. Run the App

```bash
make up
```

Open: **http://localhost:8080**

## That's It!

You now have:
- ✅ Free AI inference (no credit card)
- ✅ GPT-4o-mini (fast & smart)
- ✅ OpenAI-compatible API
- ✅ Easy migration to Azure later

## Available Models

Change `GITHUB_MODEL` in `.env`:

| Model ID | Speed | Quality | Use Case |
|----------|-------|---------|----------|
| `gpt-4o-mini` | ⚡⚡⚡ | ⭐⭐⭐ | **Recommended** - Fast, cheap |
| `gpt-4o` | ⚡⚡ | ⭐⭐⭐⭐⭐ | High quality |
| `meta-llama-3.1-70b-instruct` | ⚡⚡ | ⭐⭐⭐⭐ | Open source |

## Troubleshooting

**"No access to model"**
→ Enable `models:read` scope on your token

**"Authentication failed"**
→ Check GITHUB_TOKEN is correct in `.env`

**"Rate limit"**
→ You've hit free tier limits (generous for dev)
→ For production, migrate to Azure AI

## Next: Migrate to Azure (Optional)

When ready for production:

1. Apply to **Microsoft for Startups** ($100K-$150K credits)
2. Get Azure OpenAI credentials
3. Update `.env`:
   ```bash
   LLM_PROVIDER=azure
   AZURE_OPENAI_API_KEY=your-key
   AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
   AZURE_OPENAI_DEPLOYMENT=gpt-4o
   ```

**Same code, zero changes.** Just environment variables!

## Full Docs

- **Detailed Guide**: [docs/github-models-setup.md](docs/github-models-setup.md)
- **Main README**: [README.md](README.md)
- **Environment Config**: [.env.example](.env.example)

---

**Ready?** Run `make up` and start building!
