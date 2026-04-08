 openenv init customerSupportEnv
Creating OpenEnv environment 'customerSupportEnv'...
✓ Created 17 files

Generating uv.lock...
✓ Generated uv.lock

Environment created successfully at: V:\Developer\customerSupportEnv

Next steps:
  cd V:\Developer\customerSupportEnv
  # Edit your environment implementation in server/customerSupportEnv_environment.py
  # Edit your models in models.py
  # Install dependencies: uv sync

  # To integrate into OpenEnv repo:
  # 1. Copy this directory to <repo_root>/envs/customerSupportEnv_env
  # 2. Build from repo root: docker build -t customerSupportEnv_env:latest -f
envs/customerSupportEnv_env/server/Dockerfile .
  # 3. Run your image: docker run -p 8000:8000 customerSupportEnv_env:latest