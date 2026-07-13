# vpa-rightsizer


Agent generated with `agents-cli` version `1.0.0`

## Project Structure

```
vpa-rightsizer/
├── vpa_rightsizer/         # Core agent package
│   ├── agent.py               # Main agent logic & platform App
│   ├── fast_api_app.py        # FastAPI backend server
│   ├── app_utils/             # Telemetry, reasoning engine, and API helpers
│   └── tools/                 # Scraper, builder, and cloud/local deployer tools
├── tests/                     # Integration and server E2E tests
├── .agents/                   # Built-in agent skills
├── AGENTS.md                  # Developer guidelines and operational playbooks
├── GEMINI.md                  # AI development settings and context
├── Dockerfile                 # Production container image configuration
└── pyproject.toml             # Hatch packaging and dependency configurations
```

> 💡 **Tip:** Use [Antigravity CLI](https://antigravity.google/) for AI-assisted development - project context is pre-configured in `GEMINI.md`.

## Requirements

Before you begin, ensure you have:
- **uv**: Python package manager (used for all dependency management in this project) - [Install](https://docs.astral.sh/uv/getting-started/installation/) ([add packages](https://docs.astral.sh/uv/concepts/dependencies/) with `uv add <package>`)
- **agents-cli**: Agents CLI - Install with `uv tool install google-agents-cli`
- **Google Cloud SDK**: For GCP services - [Install](https://cloud.google.com/sdk/docs/install)


## Quick Start & Local Running

You can set up and run this agent locally in two ways depending on your preferred interface:

### ⚙️ Initial Setup
1. Install `agents-cli` and setup skills:
   ```bash
   uvx google-agents-cli setup
   agents-cli install
   ```

2. **Configure environment variables**:
   Create a local `.env` file from the template:
   ```bash
   cp .env.example .env
   ```
   Open the `.env` file and configure either Vertex AI or Gemini API credentials to prevent model connection errors. See the inline comments in `.env.example` for details.


---

### 💻 Option A: Antigravity CLI (`agy`) - Terminal TUI
The **Antigravity CLI** (`agy`) is the recommended lightweight, terminal-based conversational interface for fast, interactive testing:
1. Start the CLI:
   ```bash
   agy
   ```
2. Interact, trigger agent tools, and test agent loops directly in your shell.

---

### 🧪 Option B: Playground (`agents-cli playground`)
The **Agent CLI Playground** is a local web server with hot-reloading capabilities:
1. Start the playground:
   ```bash
   agents-cli playground
   ```
2. Open the web interface in your browser to interact with the agent. You can also inspect agent traces and steps on the fly.

You can also run native ADK commands using: `uv run adk`.

---

## 🌐 Agent Platform Publishing

Once tested locally, the agent is fully configured to be deployed and published directly to the enterprise **Agent Platform**.

### 🚀 Deployment Command
1. Configure your target Google Cloud project ID:
   ```bash
   gcloud config set project <your-project-id>
   ```
2. Deploy the agent to the platform's Agent Runtime:
   ```bash
   agents-cli deploy
   ```
3. Publish and register the agent to Gemini Enterprise:
   ```bash
   agents-cli publish gemini-enterprise
   ```

---

### 📂 Platform-Specific Files
The following files in the repository are explicitly used by and configured for the **Agent Platform** publishing process:

*   📄 **`agents-cli-manifest.yaml`**: The primary deployment manifest file used by the platform to identify the agent configuration, target region, base ADK template, runtime parameters, and workspace source directory.
*   📄 **`AGENTS.md` / `GEMINI.md`**: Behavioral guidance guidelines used by platform agents and evaluation engines to align coding practices, orchestrator loop definitions, and operational safety boundaries.
*   🐳 **`Dockerfile`**: Provides the recipe for building a container image in the platform's cloud server to run the Python ADK backend.
*   📦 **`pyproject.toml`**: Declares package dependencies, optional dependency groups (such as `eval` and `lint`), and Hatchling build targets required by the platform to correctly install and package the agent's modules during deployment.

---

## Commands

| Command              | Description                                                                                 |
| -------------------- | ------------------------------------------------------------------------------------------- |
| `agy`                | Launch the Antigravity TUI local development interface                                        |
| `agents-cli install` | Install dependencies using uv                                                         |
| `agents-cli playground` | Launch local playground development environment web server                            |
| `agents-cli lint`    | Run code quality checks                                                               |
| `agents-cli eval`    | Evaluate agent behavior (generate, grade, analyze, and more — see `agents-cli eval --help`) |
| `uv run pytest tests/unit tests/integration` | Run unit and integration tests                                                        |
| `agents-cli deploy`  | Deploy agent to the Agent Runtime platform                                                   |
| `agents-cli publish gemini-enterprise` | Register deployed agent to Gemini Enterprise                                                |
| [A2A Inspector](https://github.com/a2aproject/a2a-inspector) | Launch A2A Protocol Inspector to test interoperability                                |

---

## 🛠️ Project Management

| Command | What It Does |
|---------|--------------|
| `agents-cli scaffold enhance` | Add CI/CD pipelines and Terraform infrastructure |
| `agents-cli infra cicd` | One-command setup of entire CI/CD pipeline + infrastructure |
| `agents-cli scaffold upgrade` | Auto-upgrade to latest version while preserving customizations |

---

## Development

Edit your agent logic in `vpa_rightsizer/agent.py` and test with `agy` or `agents-cli playground` - it auto-reloads on save.

---

## Observability

Built-in telemetry exports to Cloud Trace, BigQuery, and Cloud Logging.

---

## A2A Inspector

This agent supports the [A2A Protocol](https://a2a-protocol.org/). Use the [A2A Inspector](https://github.com/a2aproject/a2a-inspector) to test interoperability.
See the [A2A Inspector docs](https://github.com/a2aproject/a2a-inspector) for details.
