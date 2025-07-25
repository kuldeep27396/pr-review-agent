# Deploy to Railway

This guide walks you through deploying the GitHub PR Review Agent to Railway.

## Prerequisites

1. **GitHub App** - Set up as described in the main README
2. **Groq API Key** - Get from [Groq Console](https://console.groq.com/) (and keep it secure!)
3. **Railway Account** - Sign up at [railway.app](https://railway.app)

## Quick Deploy

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/github.com/kuldeep27396/pr-review-agent)

## Manual Deployment Steps

### 1. Create New Project

1. Go to [Railway Dashboard](https://railway.app/dashboard)
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Connect your GitHub account if not already connected
5. Select the repository: `kuldeep27396/pr-review-agent`
6. Click "Deploy Now"

### 2. Configure Environment Variables

Railway will automatically detect the Node.js app and deploy it. You need to add these environment variables:

1. Go to your project dashboard
2. Click on your service
3. Go to "Variables" tab
4. Add the following variables:

#### Required Variables

```env
GITHUB_APP_ID=your_github_app_id
GITHUB_PRIVATE_KEY=-----BEGIN RSA PRIVATE KEY-----
your_private_key_content_here
-----END RSA PRIVATE KEY-----
GITHUB_WEBHOOK_SECRET=your_webhook_secret
GROQ_API_KEY=your_new_groq_api_key
```

#### Optional Variables (Railway will set defaults)

```env
NODE_ENV=production
PORT=3000
MAX_FILES_TO_REVIEW=10
MAX_FILE_SIZE_KB=100
REVIEW_TIMEOUT_MS=30000
LOG_LEVEL=info
```

### 3. Important Notes for Environment Variables

**For `GITHUB_PRIVATE_KEY`:**
- Copy the entire content of your downloaded `.pem` file
- Include the `-----BEGIN RSA PRIVATE KEY-----` and `-----END RSA PRIVATE KEY-----` lines
- Paste it exactly as is (Railway handles the formatting)

**Example format:**
```
-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA1234567890abcdef...
(multiple lines of the key)
...xyz789
-----END RSA PRIVATE KEY-----
```

### 4. Deploy and Get URL

1. Railway will automatically deploy your app
2. Wait for deployment to complete (usually 1-2 minutes)
3. Copy your deployment URL from Railway dashboard
4. Format: `https://your-service-name.up.railway.app`

### 5. Update GitHub App Webhook

1. Go to your GitHub App settings
2. Update webhook URL to: `https://your-service-name.up.railway.app/webhook`
3. Save changes

### 6. Test Deployment

1. **Health Check**: Visit `https://your-service-name.up.railway.app/health`
   - Should return: `{"status":"healthy","timestamp":"..."}`

2. **App Info**: Visit `https://your-service-name.up.railway.app/`
   - Should show app information

3. **Test PR Review**:
   - Install your GitHub App on a test repository
   - Create a pull request
   - Watch for automated review comments

## Configuration Files

The repository includes Railway-specific configuration:

### `railway.json`
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "npm start",
    "healthcheckPath": "/health",
    "healthcheckTimeout": 100,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

### `nixpacks.toml`
```toml
[phases.setup]
nixPkgs = ["nodejs-18_x", "npm-9_x"]

[phases.install]
cmds = ["npm ci"]

[start]
cmd = "npm start"
```

## Troubleshooting

### Common Issues

1. **Deployment Fails**
   - Check build logs in Railway dashboard
   - Verify all environment variables are set correctly
   - Ensure Node.js version compatibility

2. **Environment Variable Issues**
   - Private key must include headers/footers
   - No extra quotes around values
   - Check for trailing spaces

3. **Webhook Issues**
   - Verify webhook URL is correct and reachable
   - Check webhook secret matches exactly
   - Ensure app is running and healthy

4. **API Issues**
   - Verify Groq API key is valid and has credits
   - Check for rate limiting
   - Review app logs for detailed errors

### Monitoring

1. **Logs**: Available in Railway dashboard under "Deployments" → "View Logs"
2. **Metrics**: Check resource usage in Railway dashboard
3. **Health**: Monitor the `/health` endpoint

### Custom Domain (Optional)

1. Go to "Settings" in your Railway service
2. Click "Domains"
3. Add your custom domain
4. Update GitHub App webhook URL accordingly

## Railway Features

- **Automatic Deployments**: Updates deploy automatically on git push
- **Environment Management**: Easy variable configuration
- **Logs & Monitoring**: Built-in logging and metrics
- **Custom Domains**: Connect your own domain
- **Scaling**: Automatic scaling based on traffic

## Cost

- **Hobby Plan**: $5/month (includes $5 credit)
- **Pro Plan**: $20/month (includes $20 credit)
- **Usage-based**: Pay for what you use beyond included credits

The Hobby plan should be sufficient for most PR review workloads.

## Support

- [Railway Documentation](https://docs.railway.app/)
- [Railway Community](https://railway.app/discord)
- [GitHub Issues](https://github.com/kuldeep27396/pr-review-agent/issues)

## Security Notes

🔐 **Remember to keep your API keys secure:**
- Never share them publicly
- Use Railway's environment variables
- Regenerate if compromised
- Monitor usage regularly