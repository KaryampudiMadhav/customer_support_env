---
title: Customersupportenv Environment Server
emoji: 🥉
colorFrom: indigo
colorTo: yellow
sdk: docker
pinned: false
app_port: 8000
base_path: /web
tags:
  - openenv
---

# Customersupportenv Environment

An environment that evaluates customer support agents against company policies. Features manual debugging UI, deterministic policy grading, and hallucination detection.

## Quick Start

The simplest way to use the Customersupportenv environment is through the `CustomersupportenvEnv` class:

```python
from client import CustomersupportenvAction, CustomersupportenvEnv

try:
    # Create environment from Docker image
    customersupportenv = CustomersupportenvEnv.from_docker_image("openenv-customersupportenv:latest")

    # Reset
    result = customersupportenv.reset()
    print(f"Ticket ID: {result.observation.ticket_id}")
    print(f"Customer Message: {result.observation.customer_message}")

    # Respond to the customer
    action = CustomersupportenvAction(
        action_type="approve_refund",
        response="I've processed your refund.",
        reason="Meets unused return criteria",
        amount=99.99
    )
    result = customersupportenv.step(action)
    print(f"Reward: {result.reward}")
    print(f"Done: {result.done}")

finally:
    # Always clean up
    customersupportenv.close()
```

That's it! The `CustomersupportenvEnv.from_docker_image()` method handles:
- Starting the Docker container
- Waiting for the server to be ready
- Connecting to the environment
- Container cleanup when you call `close()`

## Building the Docker Image

Before using the environment, you need to build the Docker image:

```bash
# From project root
openenv build --tag openenv-customersupportenv
```

## Deploying to Hugging Face Spaces

You can easily deploy your OpenEnv environment to Hugging Face Spaces using the `openenv push` command:

```bash
# From the environment directory (where openenv.yaml is located)
openenv push

# Or specify options
openenv push --namespace my-org --private
```

The `openenv push` command will:
1. Validate that the directory is an OpenEnv environment (checks for `openenv.yaml`)
2. Prepare a custom build for Hugging Face Docker space (enables web interface)
3. Upload to Hugging Face (ensuring you're logged in)

### Prerequisites

- Authenticate with Hugging Face: The command will prompt for login if not already authenticated

### Options

- `--directory`, `-d`: Directory containing the OpenEnv environment (defaults to current directory)
- `--repo-id`, `-r`: Repository ID in format 'username/repo-name' (defaults to 'username/env-name' from openenv.yaml)
- `--base-image`, `-b`: Base Docker image to use (overrides Dockerfile FROM)
- `--private`: Deploy the space as private (default: public)

### Examples

```bash
# Push to your personal namespace (defaults to username/env-name from openenv.yaml)
openenv push

# Push to a specific repository
openenv push --repo-id my-org/my-env

# Push with a custom base image
openenv push --base-image ghcr.io/meta-pytorch/openenv-base:latest

# Push as a private space
openenv push --private

# Combine options
openenv push --repo-id my-org/my-env --base-image custom-base:latest --private
```

After deployment, your space will be available at:
`https://huggingface.co/spaces/<repo-id>`

The deployed space includes:
- **Web Interface** at `/web` - Interactive UI for exploring the environment
- **API Documentation** at `/docs` - Full OpenAPI/Swagger interface
- **Health Check** at `/health` - Container health monitoring
- **WebSocket** at `/ws` - Persistent session endpoint for low-latency interactions

## Environment Details

### Action
**CustomersupportenvAction**: The agent's decision logic and response.
- `response` (str) - Agent's message to the customer
- `action_type` (str) - Decision (e.g. approve_refund, request_clarification, escalate)
- `amount` (float, optional) - Refund/credit amount if applicable
- `reason` (str) - Justification for the decision from policy

### Observation
**CustomersupportenvObservation**: The state of the customer interaction.
- `customer_message` (str) - Current customer message
- `order_info` (dict) - Order details (id, amount, date, product)
- `policy_context` (str) - Relevant company policies for the issue type
- `conversation_history` (list) - Prior messages in the ticket
- `ticket_id` (str) - Unique ticket identifier
- `customer_satisfaction` (float) - Satisfaction score (0.0-1.0)
- `issue_type` (str) - Type of issue (refund, return, billing, delivery)
- `elapsed_time` (int) - Seconds spent processing the ticket

### Reward
The reward is evaluated algorithmically based on company policies:
- Strict adherence to policy logic (e.g., matching the optimal target action) (+0.6)
- Correctly matching payment/refund amounts (+0.2)
- Proper response length and tone (+0.2)
- Harsh penalties for hallucinating transaction IDs or tracking numbers (-0.5)

## Advanced Usage

### Connecting to an Existing Server

If you already have a Customersupportenv environment server running, you can connect directly:

```python
from client import CustomersupportenvEnv, CustomersupportenvAction

# Connect to existing server
customersupportenv = CustomersupportenvEnv(base_url="<ENV_HTTP_URL_HERE>")

# Use as normal
result = customersupportenv.reset()
result = customersupportenv.step(CustomersupportenvAction(
    action_type="request_clarification",
    response="Could you please confirm your order number?",
    reason="Initial request lacks details."
))
```

Note: When connecting to an existing server, `customersupportenv.close()` will NOT stop the server.

### Using the Context Manager

The client supports context manager usage for automatic connection management:

```python
from client import CustomersupportenvAction, CustomersupportenvEnv

# Connect with context manager (auto-connects and closes)
with CustomersupportenvEnv(base_url="http://localhost:8000") as env:
    result = env.reset()
    
    # Process actions
    action = CustomersupportenvAction(
        action_type="escalate",
        response="I'm transferring you to a supervisor.",
        reason="Suspicious duplicate charge amount"
    )
    result = env.step(action)
    print(f"Reward: {result.reward}")
```

The client uses WebSocket connections for:
- **Lower latency**: No HTTP connection overhead per request
- **Persistent session**: Server maintains your environment state
- **Efficient for episodes**: Better for many sequential steps

### Concurrent WebSocket Sessions

The server supports multiple concurrent WebSocket connections. To enable this,
modify `server/app.py` to use factory mode:

```python
# In server/app.py - use factory mode for concurrent sessions
app = create_app(
    CustomersupportenvEnvironment,  # Pass class, not instance
    CustomersupportenvAction,
    CustomersupportenvObservation,
    max_concurrent_envs=4,  # Allow 4 concurrent sessions
)
```

Then multiple clients can connect simultaneously:

```python
from client import CustomersupportenvAction, CustomersupportenvEnv
from concurrent.futures import ThreadPoolExecutor

def run_episode(client_id: int):
    with CustomersupportenvEnv(base_url="http://localhost:8000") as env:
        result = env.reset()
        result = env.step(CustomersupportenvAction(
            action_type="request_clarification",
            response=f"Hello from client {client_id}, how can I help?",
            reason="Triage step"
        ))
        return client_id, result.reward

# Run 4 episodes concurrently
with ThreadPoolExecutor(max_workers=4) as executor:
    results = list(executor.map(run_episode, range(4)))
```

## Development & Testing

### Direct Environment Testing

Test the environment logic directly without starting the HTTP server:

```bash
# From the server directory
python3 server/customersupportenv_environment.py
```

This verifies that:
- Environment resets correctly
- Step executes actions properly
- State tracking works
- Rewards are calculated correctly

### Running Locally

Run the server locally for development:

```bash
uvicorn server.app:app --reload
```

## Project Structure

```
customerSupportEnv/
├── .dockerignore         # Docker build exclusions
├── __init__.py            # Module exports
├── README.md              # This file
├── openenv.yaml           # OpenEnv manifest
├── pyproject.toml         # Project metadata and dependencies
├── uv.lock                # Locked dependencies (generated)
├── client.py              # CustomersupportenvEnv client
├── models.py              # Action and Observation models
└── server/
    ├── __init__.py        # Server module exports
    ├── customersupportenv_environment.py  # Core environment logic
    ├── app.py             # FastAPI application (HTTP + WebSocket endpoints)
    └── Dockerfile         # Container image definition
```
