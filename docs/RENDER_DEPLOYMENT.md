# Deploy to Render

This guide walks you through deploying the GitHub PR Review Agent to Render using the Blueprint feature.

## Prerequisites

1. **GitHub App** - Set up as described in the main README
2. **Groq API Key** - Get from [Groq Console](https://console.groq.com/)
3. **Render Account** - Sign up at [render.com](https://render.com)

## Quick Deploy

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/kuldeep27396/pr-review-agent)

## Manual Deployment Steps

### 1. Fork or Use the Repository

You can either:
- Fork this repository to your GitHub account, or
- Use the existing repository: `kuldeep27396/pr-review-agent`

### 2. Create New Web Service

1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click "New +" → "Blueprint"
3. Connect your GitHub account if not already connected
4. Select the repository: `kuldeep27396/pr-review-agent`
5. Name your Blueprint: `pr-review-agent`
6. Branch: `main`
7. Click "Submit"

### 3. Configure Environment Variables

Render will automatically detect the `render.yaml` file and set up the service. You'll need to configure these environment variables:

#### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `GITHUB_APP_ID` | Your GitHub App ID | `123456` |
| `GITHUB_PRIVATE_KEY` | Your GitHub App Private Key (PEM format) | `-----BEGIN RSA PRIVATE KEY-----\n...` |
| `GITHUB_WEBHOOK_SECRET` | Your webhook secret | `your-secret-key` |
| `GROQ_API_KEY` | Your Groq API key | `gsk_...` |

#### Optional Variables (Already Set)

| Variable | Default | Description |
|----------|---------|-------------|
| `NODE_ENV` | `production` | Environment mode |
| `PORT` | `10000` | Server port (Render default) |
| `MAX_FILES_TO_REVIEW` | `10` | Max files per PR |
| `MAX_FILE_SIZE_KB` | `100` | Max file size in KB |
| `REVIEW_TIMEOUT_MS` | `30000` | AI timeout in milliseconds |
| `LOG_LEVEL` | `info` | Logging level |

### 4. Set Environment Variables

In your Render service dashboard:

1. Go to "Environment" tab
2. Add the required environment variables:

```
GITHUB_APP_ID=your_app_id_here
GITHUB_PRIVATE_KEY=-----BEGIN RSA PRIVATE KEY-----
your_private_key_content_here
-----END RSA PRIVATE KEY-----
GITHUB_WEBHOOK_SECRET=your_webhook_secret_here
GROQ_API_KEY=your_groq_api_key_here
```

**Important**: For `GITHUB_PRIVATE_KEY`, make sure to:
- Include the full PEM format with headers and footers
- Keep the line breaks (or use `\n` for newlines)
- No quotes around the value

### 5. Deploy

1. Click "Create Web Service"
2. Render will automatically build and deploy your app
3. Wait for the deployment to complete (usually 2-3 minutes)
4. Note your service URL: `https://your-app-name.onrender.com`

### 6. Update GitHub App Webhook URL

1. Go to your GitHub App settings
2. Update the webhook URL to: `https://your-app-name.onrender.com/webhook`
3. Save the changes

### 7. Test the Deployment

1. Check the health endpoint: `https://your-app-name.onrender.com/health`
2. Should return: `{"status":"healthy","timestamp":"..."}`
3. Install your GitHub App on a test repository
4. Create a pull request to test the review functionality

## Render.yaml Configuration

The `render.yaml` file in the repository root contains:

```yaml
services:
  - type: web
    name: pr-review-agent
    runtime: node
    plan: starter
    region: oregon
    buildCommand: npm install
    startCommand: npm start
    healthCheckPath: /health
    envVars:
      - key: NODE_ENV
        value: production
      - key: PORT
        value: 10000
      # ... other environment variables
```

## Troubleshooting

### Common Issues

1. **Build Failures**
   - Check build logs in Render dashboard
   - Ensure all dependencies are in package.json
   - Verify Node.js version compatibility

2. **Environment Variable Issues**
   - Double-check all required variables are set
   - Verify private key format (PEM with proper line breaks)
   - Test variables don't have extra spaces or quotes

3. **Webhook Not Working**
   - Verify webhook URL is correct in GitHub App settings
   - Check webhook secret matches exactly
   - Review application logs in Render dashboard

4. **Health Check Failures**
   - Ensure the app starts successfully
   - Check `/health` endpoint returns 200 status
   - Review startup logs for errors

### Monitoring

- **Logs**: Available in Render dashboard under "Logs" tab
- **Metrics**: Check CPU/Memory usage in "Metrics" tab  
- **Health**: Monitor `/health` endpoint uptime

### Scaling

- **Starter Plan**: Good for testing and light usage
- **Professional Plan**: For production with more resources
- **Auto-scaling**: Available on higher plans

## Support

- [Render Documentation](https://render.com/docs)
- [GitHub Issues](https://github.com/kuldeep27396/pr-review-agent/issues)
- Check application logs for detailed error information

## Cost Estimation

- **Starter Plan**: $7/month
- **Professional Plan**: $25/month
- **Free Tier**: Available for static sites (not applicable for this Node.js app)

The Starter plan should be sufficient for most use cases unless you have very high PR volume.