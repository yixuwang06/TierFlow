# AgentFlow

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

[English](README.md) | 简体中文

双层Agent工作流系统，采用ClaudeCode（编排层）和Codex（执行层）实现长时间自主任务执行。

## 系统要求

- **Python**: 3.10 或更高版本
- **Claude Code**: 版本 <= 2.1.153（用于开发）

## 功能特性

- **双层架构**: Claude Opus负责规划/评审，GPT-5.5/DeepSeek负责执行
- **自动容灾**: GPT-5.5不可用时自动切换到DeepSeek v4 Pro
- **Skills系统**: 可扩展的领域特定任务执行（代码分析、数据处理等）
- **长时间运行**: 支持12小时以上连续运行
- **多维度完成评估**: 基于正确性、完整性、质量等指标的智能停止机制
- **灵活的模型配置**: 权限控制、优先级和自动容灾链
- **状态持久化**: 基于SQLite的状态管理和检查点机制
- **健康监控**: Prometheus指标和健康检查
- **速率限制**: 所有API的令牌桶速率限制
- **优雅关闭**: 处理SIGTERM/SIGINT信号并保存状态

## 快速开始

### 安装

```bash
# 克隆仓库
git clone <repository-url>
cd agentflow

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 配置

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑.env文件并添加你的API密钥
nano .env
```

### 使用方法

```bash
# 运行单个任务
python -m src.main run "实现用户管理的REST API"

# 守护进程模式运行（12小时以上）
python -m src.main run "持续改进代码质量" --daemon --max-iterations 1000

# 使用自定义模型配置
python -m src.main run "构建网页爬虫" --model-config config/custom.yaml

# 检查系统状态
python -m src.main status

# 查看指标
python -m src.main metrics

# 列出配置的模型
python -m src.main list-models
```

## 架构

```
┌─────────────────────────────────────────┐
│         用户请求                         │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│   ClaudeCode（编排层）                   │
│   - 任务规划与拆解                       │
│   - 结果评审                            │
│   - 完成度评估                          │
│   - 多轮迭代                            │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│   Codex（执行层）                        │
│   ┌─────────────┐    ┌───────────────┐ │
│   │  GPT-5.5    │───▶│ DeepSeek v4   │ │
│   │  (主执行器)  │    │  (备用)       │ │
│   └─────────────┘    └───────────────┘ │
└─────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│   状态管理（SQLite）                     │
│   - 工作流状态                          │
│   - 子任务追踪                          │
│   - 检查点                              │
└─────────────────────────────────────────┘
```

## 文档

- [docs/COMPLETION_MECHANISM.md](docs/COMPLETION_MECHANISM.md) - 完成评估系统
- [docs/MODEL_CONFIGURATION.md](docs/MODEL_CONFIGURATION.md) - 模型配置指南
- [docs/SKILLS_SYSTEM.md](docs/SKILLS_SYSTEM.md) - 可扩展执行的Skills系统

## 测试

### 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试
pytest tests/test_orchestrator.py -v

# 运行测试并生成覆盖率报告
pytest tests/ --cov=src --cov-report=html
```


```bash


python -m src.main run "编写一个Python函数" \
  --max-iterations 5
```

## 监控

Prometheus指标在9090端口暴露：

```bash
# 访问指标
curl http://localhost:9090/metrics
```

关键指标：
- `workflow_total`: 执行的工作流总数
- `workflow_success_total`: 成功的工作流数
- `task_duration_seconds`: 任务执行时长
- `api_requests_total`: 按模型和状态分类的API请求数
- `memory_usage_mb`: 内存使用量
- `cpu_usage_percent`: CPU使用率

## 部署

### 使用systemd

```bash
# 复制服务文件
sudo cp deployment/scow-workflow.service /etc/systemd/system/

# 启用并启动
sudo systemctl enable scow-workflow
sudo systemctl start scow-workflow
sudo systemctl status scow-workflow
```

### 使用Docker

```bash
# 构建镜像
docker build -t agentflow .

# 运行容器
docker run -d --name agentflow \
  -e ANTHROPIC_API_KEY=your_key \
  -e OPENAI_API_KEY=your_key \
  -e DEEPSEEK_API_KEY=your_key \
  -p 9090:9090 \
  agentflow
```

## 项目结构

```
agentflow/
├── src/
│   ├── api_clients/       # API客户端实现
│   ├── orchestration/     # 编排层
│   ├── execution/         # 执行层
│   ├── skills/           # Skills系统
│   ├── state/            # 状态管理
│   ├── monitoring/       # 健康监控
│   ├── config/           # 配置
│   └── utils/            # 工具函数
├── config/               # 配置文件
├── docs/                 # 文档
├── LICENSE               # MIT协议
└── README.md             # 本文件
```

## 开发

### Claude Code版本

本项目使用Claude Code版本 <= 2.1.153 开发。为获得最佳兼容性：

```bash
# 检查你的Claude Code版本
claude --version

# 如果版本 > 2.1.153，某些功能可能表现不同
# 请参考CLAUDE.md了解版本相关说明
```

## 贡献

欢迎贡献！请随时提交Pull Request。

1. Fork本仓库
2. 创建你的特性分支（`git checkout -b feature/amazing-feature`）
3. 提交你的更改（`git commit -m '添加某个很棒的特性'`）
4. 推送到分支（`git push origin feature/amazing-feature`）
5. 开启一个Pull Request

## 许可证

本项目采用MIT许可证 - 详见[LICENSE](LICENSE)文件。

## 致谢

- 使用Anthropic的[Claude](https://www.anthropic.com/claude)构建
- 支持[OpenAI](https://openai.com/)模型
- 支持[DeepSeek](https://www.deepseek.com/)模型

## 支持

如有问题和疑问：
- 在GitHub上开启issue
- 查看[文档](docs/)
- 查阅[CLAUDE.md](CLAUDE.md)获取开发指导
