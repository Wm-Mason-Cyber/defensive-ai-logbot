#!/usr/bin/env bash
# preflight.sh — check that this machine is ready for the lab.
# Run this FIRST. It never changes anything; it only reports.
set -uo pipefail

ok=0; bad=0
pass() { printf '  \033[32m✓\033[0m %s\n' "$1"; ok=$((ok+1)); }
fail() { printf '  \033[31m✗\033[0m %s\n    → %s\n' "$1" "$2"; bad=$((bad+1)); }

echo "Defensive AI Lab — preflight check"
echo "──────────────────────────────────"

# Docker
if command -v docker >/dev/null && docker info >/dev/null 2>&1; then
    pass "Docker is installed and running"
else
    fail "Docker not available" "Start Docker Desktop and enable WSL integration, then re-run."
fi

# docker compose v2
if docker compose version >/dev/null 2>&1; then
    pass "docker compose (v2) available"
else
    fail "docker compose v2 not found" "Update Docker Desktop (Compose ships with it)."
fi

# Ollama
if command -v ollama >/dev/null 2>&1; then
    pass "ollama installed"
    if curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
        pass "ollama server is reachable"
        if ollama list 2>/dev/null | grep -q 'llama3.2:3b'; then
            pass "model llama3.2:3b is pulled"
        else
            fail "model llama3.2:3b missing" "Run: ollama pull llama3.2:3b"
        fi
    else
        fail "ollama server not reachable" "Run 'ollama serve' (or start the Ollama app)."
    fi
else
    fail "ollama not installed" "Install from https://ollama.com/download then: ollama pull llama3.2:3b"
fi

# Python + ollama package
if command -v python3 >/dev/null 2>&1; then
    pass "python3 installed ($(python3 --version 2>&1 | awk '{print $2}'))"
    if python3 -c "import ollama" 2>/dev/null; then
        pass "python 'ollama' package installed"
    else
        fail "python 'ollama' package missing" "Run: pip install ollama  (add --break-system-packages if pip refuses)"
    fi
else
    fail "python3 not installed" "Install python3 in your WSL distro: sudo apt install python3 python3-pip"
fi

# GPU (optional, informational)
if command -v nvidia-smi >/dev/null 2>&1; then
    gpu=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null | head -1)
    pass "GPU detected: ${gpu:-unknown} (nice — inference will be fast)"
else
    printf '  \033[33m•\033[0m No NVIDIA GPU detected — the model will run on CPU (slower, still works)\n'
fi

echo "──────────────────────────────────"
if [ "$bad" -eq 0 ]; then
    printf '\033[32mAll %d checks passed. You are ready: ./scripts/run_lab.sh\033[0m\n' "$ok"
    exit 0
else
    printf '\033[31m%d check(s) need attention (see → hints above).\033[0m\n' "$bad"
    exit 1
fi
