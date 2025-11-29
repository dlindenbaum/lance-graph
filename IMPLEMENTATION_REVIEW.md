# Implementation Review: Graph Review UI with LiteLLM Router

## Overview

This document reviews the Graph Review UI implementation and details the LiteLLM Router strategy for multi-model support.

## ✅ What's Good

### 1. **Frontend Architecture**
- **Clean Component Structure**: Well-separated concerns with dedicated components for each UI element
- **Type Safety**: Full TypeScript coverage with comprehensive type definitions
- **State Management**: Custom hook (`useGraphReview`) centralizes all state logic
- **User Experience**:
  - Inline editing before approval
  - Evidence panels with confidence scores
  - Quick action buttons for common queries
  - Dark theme optimized for long sessions

### 2. **Backend Design**
- **LiteLLM Router Integration**: ✅ Now properly implemented
- **Tool System**: Modular tools for graph queries and CDR analysis
- **FastAPI Integration**: Clean separation with component-based architecture
- **WebSocket Support**: Real-time agent communication

### 3. **Multi-Model Support** (NEW)

#### LiteLLM Router Benefits
1. **Automatic Fallbacks**: If primary model fails, automatically falls back to secondary models
2. **Load Balancing**: Distributes requests across models based on strategy
3. **Retry Logic**: Automatically retries failed requests
4. **Cost Tracking**: Monitor usage across different models
5. **Flexibility**: Easy to add/remove models via configuration

#### Routing Strategies

**1. usage-based-routing (Default)**
- Routes to model with lowest cumulative usage
- Best for: Cost optimization, even distribution

**2. simple-shuffle**
- Randomly distributes requests
- Best for: Simple load balancing

**3. least-busy**
- Routes to model with fewest active requests
- Best for: Performance optimization

**4. latency-based-routing**
- Routes to fastest responding model
- Best for: Response time optimization

### 4. **Configuration System**

Environment-based configuration with fallbacks:

```python
# Automatic model detection from environment
config = AgentConfig.from_env()

# Models automatically configured if API keys present:
# 1. OpenAI (if OPENAI_API_KEY set)
# 2. Google Gemini (if GEMINI_API_KEY set)
# 3. Anthropic Claude (if ANTHROPIC_API_KEY set)
# 4. Azure OpenAI (if AZURE_API_KEY set)
```

## 📋 Architecture

### Component Flow

```
User Input → Frontend (React)
     ↓
 WebSocket/HTTP
     ↓
 FastAPI Router → GraphReviewAgentComponent
     ↓
 CDRInvestigationAgent (with LiteLLM Router)
     ↓
 ┌─────────────────────┐
 │  LiteLLM Router     │
 │  ┌───────────────┐  │
 │  │ Model 1: GPT  │  │ ← Primary
 │  ├───────────────┤  │
 │  │ Model 2: Gem  │  │ ← Fallback 1
 │  ├───────────────┤  │
 │  │ Model 3: Clau │  │ ← Fallback 2
 │  └───────────────┘  │
 └─────────────────────┘
     ↓
 Tools: GraphQueryTool, CDRAnalysisTool
     ↓
 lance-graph Backend
```

### Model Selection Flow

```
Request → Router
    │
    ├─ Check routing_strategy
    │   ├─ usage-based → Select lowest usage model
    │   ├─ least-busy → Select model with fewest active requests
    │   ├─ latency-based → Select fastest model
    │   └─ simple-shuffle → Random selection
    │
    ├─ Attempt request to selected model
    │   │
    │   ├─ Success → Return response
    │   │
    │   └─ Failure → Check fallback chain
    │       ├─ Try fallback model 1
    │       ├─ Try fallback model 2
    │       └─ Return error if all fail
    │
    └─ Log usage/latency stats
```

## 🔧 Configuration Examples

### Example 1: Cost-Optimized (Free/Cheap Models)

```yaml
router:
  routing_strategy: "usage-based-routing"
  models:
    - model_name: gemini/gemini-1.5-flash
      litellm_params:
        api_key: ${GEMINI_API_KEY}
    - model_name: gpt-4o-mini
      litellm_params:
        api_key: ${OPENAI_API_KEY}
  fallbacks:
    - gemini/gemini-1.5-flash: [gpt-4o-mini]
```

### Example 2: Quality-Optimized (Best Models)

```yaml
router:
  routing_strategy: "latency-based-routing"
  models:
    - model_name: gpt-4o
      litellm_params:
        api_key: ${OPENAI_API_KEY}
    - model_name: claude-3-5-sonnet-20241022
      litellm_params:
        api_key: ${ANTHROPIC_API_KEY}
    - model_name: gemini/gemini-1.5-pro
      litellm_params:
        api_key: ${GEMINI_API_KEY}
  fallbacks:
    - gpt-4o: [claude-3-5-sonnet-20241022, gemini/gemini-1.5-pro]
```

### Example 3: Enterprise (Azure + Fallbacks)

```yaml
router:
  routing_strategy: "least-busy"
  models:
    - model_name: azure/gpt-4o
      litellm_params:
        api_key: ${AZURE_API_KEY}
        api_base: ${AZURE_API_BASE}
    - model_name: gpt-4o-mini
      litellm_params:
        api_key: ${OPENAI_API_KEY}
  fallbacks:
    - azure/gpt-4o: [gpt-4o-mini]
```

## 🎯 Use Cases

### 1. **High Availability**
- **Problem**: Single model can have outages
- **Solution**: Configure 3+ models with fallback chain
- **Strategy**: `simple-shuffle` for even distribution

### 2. **Cost Optimization**
- **Problem**: Need to minimize LLM costs
- **Solution**: Use cheap models (gemini-flash, gpt-4o-mini) as primary
- **Strategy**: `usage-based-routing` to distribute load

### 3. **Performance Critical**
- **Problem**: Need fastest response times
- **Solution**: Configure multiple fast models
- **Strategy**: `latency-based-routing` to use fastest

### 4. **Load Balancing**
- **Problem**: Rate limits on single model
- **Solution**: Configure multiple instances of same model
- **Strategy**: `least-busy` to distribute across instances

## 🔍 Monitoring & Debugging

### Agent Status Endpoint

```bash
curl http://localhost:8000/api/agent/status
```

Returns:
```json
{
  "status": "ready",
  "iteration_count": 5,
  "conversation_length": 12,
  "router": {
    "models": ["gpt-4o-mini", "gemini/gemini-1.5-flash"],
    "routing_strategy": "usage-based-routing",
    "fallbacks_configured": true
  },
  "config": {
    "temperature": 0.7,
    "max_tokens": 2000,
    "routing_strategy": "usage-based-routing"
  }
}
```

### Logging

Set `AGENT_LOG_LEVEL=DEBUG` to see:
- Model selection decisions
- Fallback attempts
- Token usage
- Latency metrics

```python
# In logs:
INFO - Using router with strategy: usage-based-routing
INFO - Initialized LiteLLM Router with 2 models: ['gpt-4o-mini', 'gemini/gemini-1.5-flash']
INFO - Token usage: {'prompt_tokens': 145, 'completion_tokens': 87, 'total_tokens': 232}
```

## ⚠️ Considerations & Limitations

### 1. **API Key Management**
- **Issue**: Multiple API keys to manage
- **Solution**: Use environment variables or secrets manager
- **Best Practice**: Rotate keys regularly

### 2. **Model Compatibility**
- **Issue**: Different models have different capabilities
- **Solution**: Use `model_info.supports_function_calling` flag
- **Note**: Current implementation works with chat-based models

### 3. **Cost Tracking**
- **Issue**: Need to track costs across models
- **Solution**: LiteLLM router logs usage, integrate with cost tracking
- **TODO**: Add cost tracking dashboard

### 4. **Rate Limits**
- **Issue**: Each model has different rate limits
- **Solution**: Configure retry_policy and cooldown_time
- **Best Practice**: Set conservative timeouts

### 5. **Response Quality**
- **Issue**: Different models may give different quality responses
- **Solution**: Configure higher-quality models as primary
- **Fallback**: Lower quality models for availability

## 🚀 Deployment Recommendations

### Development
```bash
# Use single cheap model
export OPENAI_API_KEY=sk-...
export LITELLM_ROUTING_STRATEGY=simple-shuffle
```

### Staging
```bash
# Use 2 models with fallback
export OPENAI_API_KEY=sk-...
export GEMINI_API_KEY=...
export LITELLM_ROUTING_STRATEGY=usage-based-routing
```

### Production
```bash
# Use 3+ models with comprehensive fallbacks
export OPENAI_API_KEY=sk-...
export GEMINI_API_KEY=...
export ANTHROPIC_API_KEY=...
export AZURE_API_KEY=...
export AZURE_API_BASE=https://...
export LITELLM_ROUTING_STRATEGY=latency-based-routing
export AGENT_LOG_LEVEL=INFO
```

## 📊 Performance Characteristics

| Strategy | Latency | Cost | Availability | Use Case |
|----------|---------|------|--------------|----------|
| simple-shuffle | Medium | Medium | High | General purpose |
| usage-based-routing | Medium | Low | High | Cost optimization |
| least-busy | Low | Medium | High | High load |
| latency-based-routing | Low | High | Medium | Performance critical |

## ✅ Validation Checklist

- [x] Router properly configured
- [x] Fallback chain tested
- [x] Retry logic implemented
- [x] Error handling comprehensive
- [x] Logging properly configured
- [x] Environment variables documented
- [x] Status endpoint functional
- [x] Multiple model support tested
- [x] Cost tracking capability
- [x] Frontend integration complete

## 🎯 Recommendations

1. **Start Simple**: Begin with 1-2 models, add more as needed
2. **Monitor Costs**: Track usage across models
3. **Test Fallbacks**: Ensure fallback chain works
4. **Use Appropriate Strategy**: Match strategy to use case
5. **Configure Timeouts**: Set reasonable retry limits
6. **Log Everything**: Enable comprehensive logging
7. **Rotate Keys**: Regular API key rotation
8. **Track Quality**: Monitor response quality across models

## 📚 References

- [LiteLLM Router Documentation](https://docs.litellm.ai/docs/routing)
- [Supported Models](https://docs.litellm.ai/docs/providers)
- [FastAPI Best Practices](https://fastapi.tiangolo.com/deployment/)
