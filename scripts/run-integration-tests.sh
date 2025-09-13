#!/bin/bash

# Run integration tests that use REAL Ollama models
# This will actually hit your RTX 5070 GPU!

echo "🚀 Running Integration Tests with REAL Ollama Models"
echo "=================================================="
echo "⚡ This will use your RTX 5070 GPU through Ollama"
echo "🔥 Make sure Ollama is running: ollama serve"
echo ""

# Check if Ollama is running
if ! curl -s http://localhost:11434/api/tags > /dev/null; then
    echo "❌ Ollama is not running on localhost:11434"
    echo "   Start it with: ollama serve"
    exit 1
fi

echo "✅ Ollama is running"
echo ""

# Show available models
echo "📋 Available Ollama models:"
curl -s http://localhost:11434/api/tags | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    for model in data.get('models', []):
        print(f'   - {model[\"name\"]}')
except:
    print('   Could not list models')
"
echo ""

# Run fast integration tests (no LLM calls)
echo "🧪 Running fast integration tests (no GPU usage)..."
python -m pytest langgraph_workflow/tests/test_real_ollama_integration.py::TestRealOllamaIntegration::test_real_feature_extraction -v
python -m pytest langgraph_workflow/tests/test_real_ollama_integration.py::TestRealOllamaIntegration::test_real_codebase_analysis -v

echo ""
echo "🔥 Running REAL Ollama integration tests (GPU will be active)..."
echo "   Watch your GPU usage: nvidia-smi"
echo ""

# Run tests that actually hit Ollama
python -m pytest langgraph_workflow/tests/test_real_ollama_integration.py::TestRealOllamaIntegration::test_real_ollama_code_context_generation -v -s
python -m pytest langgraph_workflow/tests/test_real_ollama_integration.py::TestRealOllamaIntegration::test_real_agent_analysis -v -s

echo ""
echo "🎉 Integration tests completed!"
echo "💡 To run only unit tests (no GPU): pytest -m 'not integration'"
echo "💡 To run only integration tests: pytest -m integration"