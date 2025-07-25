# GitHub PR Review Agent 🤖

An automated GitHub PR review agent powered by Groq AI that provides intelligent code reviews as soon as pull requests are created or updated. Built to work like CodeRabbit, but free and self-hosted.

## ✨ Features

- 🔄 **Automatic PR Reviews**: Reviews PRs immediately when opened or updated
- 🧠 **AI-Powered Analysis**: Uses Groq's fast LLaMA models for intelligent code analysis
- 🎯 **Smart Filtering**: Only reviews relevant files and respects size limits
- 💬 **Contextual Comments**: Provides line-specific feedback with severity levels
- 🔒 **Security Focus**: Identifies potential security vulnerabilities
- ⚡ **Performance Insights**: Highlights performance concerns
- 🎨 **Code Quality**: Checks for best practices and code style
- 📊 **Comprehensive Reporting**: Generates overall PR summaries
- 🚀 **Easy Deployment**: One-click deploy to popular hosting platforms
- ⚙️ **Configurable**: Customizable review parameters and file limits

## 🚀 Quick Start

### Option 1: One-Click Deploy

Deploy to your preferred platform:

[![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/kuldeep27396/pr-review-agent)
[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template?template=https://github.com/kuldeep27396/pr-review-agent)
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/kuldeep27396/pr-review-agent)

### Option 2: Manual Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/kuldeep27396/pr-review-agent.git
   cd pr-review-agent
   npm install
   ```

2. **Set up your GitHub App**
   ```bash
   node scripts/setup-github-app.js
   ```
   This will guide you through creating a GitHub App and configuring the environment.

3. **Start the application**
   ```bash
   npm start
   ```

## 📋 Prerequisites

### GitHub App Setup

1. Go to [GitHub Apps](https://github.com/settings/apps/new) and create a new app with:
   - **App name**: `Your PR Review Agent`
   - **Homepage URL**: Your deployment URL
   - **Webhook URL**: `https://your-domain.com/webhook`
   - **Webhook secret**: Generate a secure random string

2. **Set these permissions**:
   - Repository permissions:
     - Contents: Read
     - Pull requests: Write
     - Metadata: Read

3. **Subscribe to events**:
   - Pull request
   - Pull request review

4. **Download the private key** and note your App ID

### Groq API Key

1. Sign up at [Groq Console](https://console.groq.com/)
2. Create an API key
3. Note the key for configuration

## ⚙️ Configuration

### Environment Variables

Create a `.env` file with:

```env
# GitHub App Configuration (Required)
GITHUB_APP_ID=your_github_app_id
GITHUB_PRIVATE_KEY=your_github_private_key
GITHUB_WEBHOOK_SECRET=your_webhook_secret

# Groq API Configuration (Required)
GROQ_API_KEY=your_groq_api_key

# Server Configuration
PORT=3000
NODE_ENV=production

# Review Settings (Optional)
MAX_FILES_TO_REVIEW=10
MAX_FILE_SIZE_KB=100
REVIEW_TIMEOUT_MS=30000
LOG_LEVEL=info
```

### Supported File Types

The agent reviews these file types:
- **JavaScript/TypeScript**: `.js`, `.jsx`, `.ts`, `.tsx`
- **Python**: `.py`
- **Java**: `.java`
- **C/C++**: `.c`, `.cpp`, `.h`
- **C#**: `.cs`
- **PHP**: `.php`
- **Ruby**: `.rb`
- **Go**: `.go`
- **Rust**: `.rs`
- **Swift**: `.swift`
- **Kotlin**: `.kt`
- **Scala**: `.scala`
- **Vue**: `.vue`
- **Svelte**: `.svelte`
- **Dart**: `.dart`
- **R**: `.r`
- **SQL**: `.sql`
- **Shell**: `.sh`
- **Config**: `.yaml`, `.yml`, `.json`, `.xml`
- **Web**: `.html`, `.css`, `.scss`, `.less`

## 📖 How It Works

1. **PR Detection**: Listens for PR opened/updated webhooks from GitHub
2. **File Analysis**: Fetches changed files and filters reviewable content
3. **AI Review**: Sends code to Groq AI for analysis with structured prompts
4. **Comment Generation**: Creates contextual comments with severity levels
5. **Review Posting**: Posts comprehensive review back to GitHub PR

### Review Categories

- 🐛 **Bugs**: Potential runtime errors and logical issues
- 🔒 **Security**: Security vulnerabilities and concerns
- ⚡ **Performance**: Performance bottlenecks and optimizations
- 🎨 **Style**: Code style and formatting issues
- ✅ **Best Practices**: Code quality and maintainability

### Severity Levels

- 🔴 **High**: Critical issues requiring immediate attention
- 🟡 **Medium**: Important issues that should be addressed
- 🟢 **Low**: Minor improvements and suggestions

## 🔧 Development

### Local Development

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Run tests
npm test
```

### Docker Development

```bash
# Build and run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f
```

### Project Structure

```
github-pr-review-agent/
├── src/
│   ├── index.js              # Main application entry
│   ├── services/
│   │   ├── github.js         # GitHub API integration
│   │   ├── groq.js           # Groq AI service
│   │   └── review.js         # Review orchestration
│   └── utils/
│       └── logger.js         # Logging utility
├── scripts/
│   └── setup-github-app.js   # Setup helper script  
├── docs/
│   └── DEPLOYMENT.md         # Deployment guide
├── .github/workflows/        # CI/CD workflows
├── Dockerfile               # Container configuration
├── docker-compose.yml       # Local development setup
└── app.json                # Heroku deployment config
```

## 📚 API Endpoints

- `GET /` - Application info and status
- `GET /health` - Health check endpoint
- `POST /webhook` - GitHub webhook handler

## 🔍 Monitoring

### Health Checks

The application provides health monitoring:
- **Health endpoint**: `GET /health`
- **Status codes**: 200 (healthy), 500 (unhealthy)
- **Response**: JSON with status and timestamp

### Logging

Logs are written to the `logs/` directory:
- `all.log` - All log messages
- `info.log` - Info level and above
- `warn.log` - Warning level and above
- `error.log` - Error messages only

Set log level with `LOG_LEVEL` environment variable (error/warn/info/debug).

## 🤝 Contributing

We welcome contributions! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 🐛 Troubleshooting

### Common Issues

**Webhook not receiving events**
- Verify webhook URL is accessible from the internet
- Check webhook secret matches your configuration
- Ensure the GitHub App is installed on your repositories

**Authentication errors**
- Verify GitHub App ID and private key are correct
- Check app permissions include Contents (read) and Pull requests (write)
- Ensure private key format includes proper newlines

**Groq API errors**
- Verify API key is valid and has credits
- Check rate limits aren't exceeded
- Ensure access to llama3-8b-8192 model

**Reviews not posting**
- Check GitHub App installation and permissions
- Verify webhook events are being received
- Review application logs for errors

### Getting Help

- Check the [Deployment Guide](docs/DEPLOYMENT.md) for detailed setup instructions
- See [Railway Deployment Guide](docs/RAILWAY_DEPLOYMENT.md) for Railway-specific instructions
- See [Render Deployment Guide](docs/RENDER_DEPLOYMENT.md) for Render-specific instructions
- Review application logs in the `logs/` directory
- Open an issue on GitHub for bugs or feature requests

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Groq](https://groq.com/) for providing fast AI inference
- [Octokit](https://octokit.github.io/) for GitHub API integration
- [CodeRabbit](https://coderabbit.ai/) for inspiration

---

**Made with ❤️ for the developer community**

*Star ⭐ this repo if you find it useful!*
