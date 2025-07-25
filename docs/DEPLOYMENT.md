# Deployment Guide

This guide covers different deployment options for the GitHub PR Review Agent.

## Quick Deploy Options

### Deploy to Heroku (Recommended)

[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/your-username/github-pr-review-agent)

1. Click the "Deploy to Heroku" button above
2. Fill in the required environment variables:
   - `GITHUB_APP_ID`: Your GitHub App ID
   - `GITHUB_PRIVATE_KEY`: Your GitHub App Private Key (PEM format)
   - `GITHUB_WEBHOOK_SECRET`: Your webhook secret
   - `GROQ_API_KEY`: Your Groq API key
3. Deploy and note your app URL
4. Update your GitHub App webhook URL to `https://your-app.herokuapp.com/webhook`

### Deploy to Railway

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template?template=https://github.com/kuldeep27396/pr-review-agent)

### Deploy to Render

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/kuldeep27396/pr-review-agent)

## Manual Deployment

### Prerequisites

- Node.js 18+ 
- npm or yarn
- A GitHub App (see setup instructions below)
- A Groq API key

### Local Development

1. Clone the repository:
   ```bash
   git clone https://github.com/kuldeep27396/pr-review-agent.git
   cd pr-review-agent
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. Run the setup script:
   ```bash
   node scripts/setup-github-app.js
   ```

5. Start the development server:
   ```bash
   npm run dev
   ```

### Docker Deployment

1. Build the Docker image:
   ```bash
   docker build -t github-pr-review-agent .
   ```

2. Run with docker-compose:
   ```bash
   docker-compose up -d
   ```

### VPS/Server Deployment

1. Set up your server (Ubuntu/Debian example):
   ```bash
   # Install Node.js
   curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
   sudo apt-get install -y nodejs
   
   # Install PM2 for process management
   sudo npm install -g pm2
   ```

2. Deploy your application:
   ```bash
   git clone https://github.com/kuldeep27396/pr-review-agent.git
   cd pr-review-agent
   npm install --production
   ```

3. Configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your production configuration
   ```

4. Start with PM2:
   ```bash
   pm2 start src/index.js --name "github-pr-review-agent"
   pm2 save
   pm2 startup
   ```

5. Set up reverse proxy (nginx example):
   ```nginx
   server {
       listen 80;
       server_name your-domain.com;
       
       location / {
           proxy_pass http://localhost:3000;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection 'upgrade';
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
           proxy_cache_bypass $http_upgrade;
       }
   }
   ```

## Environment Variables

Required:
- `GITHUB_APP_ID`: Your GitHub App ID
- `GITHUB_PRIVATE_KEY`: Your GitHub App Private Key (PEM format)
- `GITHUB_WEBHOOK_SECRET`: Your webhook secret
- `GROQ_API_KEY`: Your Groq API key

Optional:
- `PORT`: Server port (default: 3000)
- `NODE_ENV`: Environment (production/development)
- `MAX_FILES_TO_REVIEW`: Maximum files per PR (default: 10)
- `MAX_FILE_SIZE_KB`: Maximum file size in KB (default: 100)
- `REVIEW_TIMEOUT_MS`: AI review timeout (default: 30000)
- `LOG_LEVEL`: Logging level (error/warn/info/debug)

## Health Checks

The application provides health check endpoints:

- `GET /health`: Basic health check
- `GET /`: Application info and status

## Monitoring

The application creates logs in the `logs/` directory:
- `all.log`: All log messages
- `info.log`: Info level and above
- `warn.log`: Warning level and above  
- `error.log`: Error messages only

## Troubleshooting

### Common Issues

1. **Webhook not receiving events**
   - Check your webhook URL is correct
   - Verify the webhook secret matches
   - Ensure your app is installed on the repository

2. **Authentication errors**
   - Verify your GitHub App ID and private key
   - Check that your app has the correct permissions
   - Ensure the private key format is correct (PEM with newlines)

3. **Groq API errors**
   - Verify your API key is valid
   - Check rate limits and quotas
   - Ensure you have access to the llama3-8b-8192 model

4. **File too large errors**
   - Adjust `MAX_FILE_SIZE_KB` and `MAX_FILES_TO_REVIEW`
   - Consider filtering file types in the code

### Logs and Debugging

Enable debug logging:
```bash
export LOG_LEVEL=debug
```

Check application logs:
```bash
# PM2
pm2 logs github-pr-review-agent

# Docker
docker-compose logs -f

# Direct
tail -f logs/all.log
```