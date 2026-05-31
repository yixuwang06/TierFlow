# AgentFlow

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

English | [简体中文](README_zh.md)

Two-tier agent workflow system with ClaudeCode (orchestration) and Codex (execution) for long-running autonomous task execution.

## Requirements

- **Python**: 3.10 or higher
- **Claude Code**: Version <= 2.1.153 (for development)

## Features

- **Two-tier architecture**: Claude Opus for planning/review, GPT-5.5/DeepSeek for execution
- **Automatic failover**: Switches to DeepSeek v4 Pro when GPT-5.5 is unavailable
- **Skills system**: Extensible domain-specific task execution (code analysis, data processing, etc.)
- **Long-running support**: Designed for 12+ hour continuous operation
- **Multi-dimensional completion**: Smart stopping with correctness, completeness, quality metrics
- **Flexible model configuration**: Permissions, priorities, and automatic fallback chains
- **State persistence**: SQLite-based state management with checkpointing
- **Health monitoring**: Prometheus metrics and health checks
- **Rate limiting**: Token bucket rate limiting for all APIs
- **Graceful shutdown**: Handles SIGTERM/SIGINT with state preservation

## Quick Start

### Installation

```bash
# Clone repository
git clone <repository-url>
cd agentflow

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env and add your API keys
nano .env
```

### Usage

```bash
# Run a single task
python -m src.main run "Implement a REST API for user management"

# Run in daemon mode (12+ hours)
python -m src.main run "Continuously improve code quality" --daemon --max-iterations 1000

# Use custom model configuration
python -m src.main run "Build a web scraper" --model-config config/custom.yaml

# Check system status
python -m src.main status

# View metrics
python -m src.main metrics

# List configured models
python -m src.main list-models
```

## Architecture

```
┌─────────────────────────────────────────┐
│         User Request                    │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│   ClaudeCode (Orchestration Layer)      │
│   - Task planning & decomposition       │
│   - Result review                       │
│   - Completion evaluation               │
│   - Multi-round iteration               │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│   Codex (Execution Layer)               │
│   ┌─────────────┐    ┌───────────────┐ │
│   │  GPT-5.5    │───▶│ DeepSeek v4   │ │
│   │  (Primary)  │    │  (Fallback)   │ │
│   └─────────────┘    └───────────────┘ │
└─────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│   State Management (SQLite)             │
│   - Workflow state                      │
│   - Subtask tracking                    │
│   - Checkpoints                         │
└─────────────────────────────────────────┘
```

## Documentation

- [docs/COMPLETION_MECHANISM.md](docs/COMPLETION_MECHANISM.md) - Completion evaluation system
- [docs/MODEL_CONFIGURATION.md](docs/MODEL_CONFIGURATION.md) - Model configuration guide
- [docs/SKILLS_SYSTEM.md](docs/SKILLS_SYSTEM.md) - Skills system for extensible execution

## Testing

### Run Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test
pytest tests/test_orchestrator.py -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```


```bash


python -m src.main run "Write a Python function" \
  --max-iterations 5
```

## Monitoring

Prometheus metrics are exposed on port 9090:

```bash
# Access metrics
curl http://localhost:9090/metrics
```

Key metrics:
- `workflow_total`: Total workflows executed
- `workflow_success_total`: Successful workflows
- `task_duration_seconds`: Task execution duration
- `api_requests_total`: API requests by model and status
- `memory_usage_mb`: Memory usage
- `cpu_usage_percent`: CPU usage

## Deployment

### Using systemd

```bash
# Copy service file
sudo cp deployment/scow-workflow.service /etc/systemd/system/

# Enable and start
sudo systemctl enable scow-workflow
sudo systemctl start scow-workflow
sudo systemctl status scow-workflow
```

### Using Docker

```bash
# Build image
docker build -t agentflow .

# Run container
docker run -d --name agentflow \
  -e ANTHROPIC_API_KEY=your_key \
  -e OPENAI_API_KEY=your_key \
  -e DEEPSEEK_API_KEY=your_key \
  -p 9090:9090 \
  agentflow
```

## Project Structure

```
agentflow/
├── src/
│   ├── api_clients/       # API client implementations
│   ├── orchestration/     # Orchestration layer
│   ├── execution/         # Execution layer
│   ├── skills/           # Skills system
│   ├── state/            # State management
│   ├── monitoring/       # Health monitoring
│   ├── config/           # Configuration
│   └── utils/            # Utilities
├── config/               # Configuration files
├── docs/                 # Documentation
├── LICENSE               # MIT License
└── README.md             # This file
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [Claude](https://www.anthropic.com/claude) by Anthropic
- Supports [OpenAI](https://openai.com/) models
- Supports [DeepSeek](https://www.deepseek.com/) models

## Support

For issues and questions:
- Open an issue on GitHub
- Check the [documentation](docs/)
- Review [CLAUDE.md](CLAUDE.md) for development guidance
