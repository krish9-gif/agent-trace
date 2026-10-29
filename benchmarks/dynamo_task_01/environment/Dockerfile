FROM python:3.11-slim

# Security: Non-root user isolation
RUN useradd -m -u 1000 sandbox_user

WORKDIR /workspace

# Install baseline dependencies
RUN pip install --no-cache-dir pytest>=8.0.0

# Prepare workspace directory permissions
RUN mkdir -p /workspace/data && chown -R sandbox_user:sandbox_user /workspace

# Copy task input data strictly into environment
COPY --chown=sandbox_user:sandbox_user data/events.jsonl /workspace/data/events.jsonl

USER sandbox_user

CMD ["/bin/bash"]
