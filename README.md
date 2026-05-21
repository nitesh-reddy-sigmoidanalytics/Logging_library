# SmartLLMOps SDK

A lightweight, declarative, and framework-agnostic SDK for high-fidelity tracing and observability in RAG and Agentic LLM applications.

## 🚀 Installation

### 1. Local Development
To install the SDK in your application's environment during development:
```bash
pip install -e /path/to/smartllmops-sdk
```

### 2. From Source (Production)
```bash
pip install git+https://github.com/srishtisingh2026/Logging_library.git
```

## ⚙️ Configuration (Zero-Config Library Loading)

All database connection credentials are **automatically and explicitly loaded by the SDK from the logging library's own `.env` file** upon import. 

**There is absolutely no need to define, set up, or pass connection credentials inside your monitored application's workspace or system environment.** The database endpoints are fully managed and encapsulated within the library!

| Variable | Location | Description | Default |
|----------|----------|-------------|---------|
| `COSMOS_CONN_WRITE` | Library's `.env` | Primary connection string for Azure Cosmos DB | *Pre-configured* |
| `COSMOS_DB` | Library's `.env` | Database name | `llmops-data` |
| `COSMOS_CONTAINER` | Library's `.env` | Container name | `raw_traces` |
| `SMART_LLMOPS_APP` | Application environment | Application name for grouping traces | `default-app` |

---

## 🛠️ Quick Start

### 1. Initialize the Tracer
Simply call `init()` without database arguments in your monitored application. The SDK automatically resolves the pre-configured parameters from its internal settings.

```python
import smartllmops

# No need to manage Cosmos credentials—they are loaded natively by the library!
tracer = smartllmops.init(
    application_name="my-portfolio-analyst",
    environment="production",
    framework="langchain",  # Optional: logs framework source at trace level
    tags={"version": "1.0.2", "team": "fin-tech"}
)
```

### 2. Decorate your Functions
Use the `@trace` decorator to capture execution flow, parent-child hierarchies, latencies, and metadata.

```python
@tracer.trace(span_type="llm", name="my_llm_span")
def get_llm_response(prompt):
    # Your LLM call logic
    return content, prompt, usage_metadata
```

---

## 📊 AI Execution Telemetry & Semantic Layer

Rather than flattening AI traces into generic spans, the SDK enforces a **canonical semantic layer** mapping application-defined subtypes to standard high-level AI operation types.

### Canonical Taxonomy (`observation_type`)
* `GENERATION` — Text generations and completions (standardized with `gen_ai.operation.name="chat"`)
* `RETRIEVER` — Database or document search (standardized with `gen_ai.operation.name="retrieve"`)
* `TOOL` — External tool/function execution (standardized with `gen_ai.tool.name`)
* `AGENT` — LLM reasoning, decision-making, and planners (standardized with `gen_ai.agent.name`)
* `CHAIN` — Sequential pipeline workflows and prompt rewrites
* `SPAN` — Standard application execution trace
* `EMBEDDING` / `EVALUATOR` / `GUARDRAIL` / `EVENT`

### Auto-Enriched Metadata
Spans logged under specific subtypes are automatically parsed and structured:
* **`llm` / `chat-completion`**: Extracts model name, system tags, raw token counts, and token cost variables.
* **`retrieval`**: Extracts document snippets, scores, similarity distances, and parses document fields (`page_content`, `text`, `content`) for full framework interoperability.
* **`workflow` step parameters**: Automatically maps `step_number` to `workflow.step` and `iteration` to `workflow.iteration`.

---

## 🔄 Trace Life Cycle
Wrap your master pipeline run with standard trace initialization and export methods.

```python
def run_pipeline(user_query):
    # A. Start a new trace context
    tracer.start_trace()
    
    try:
        # B. Run your logic (decorated spans will naturally nest hierarchically)
        result = my_rag_engine.run(user_query)
        
        # C. Export the completed trace
        tracer.export_trace(
            result, 
            query=user_query, 
            session_id="session-123", 
            user_id="user-456"
        )
        return result
    except Exception as e:
        raise e
```

---

## 🔄 User Feedback & Browser Auto-Capture

SmartLLMOps supports zero-config client-side user feedback capturing (Thumbs Up/Down, Copy, and Retry clicks). Rather than rendering proprietary button layouts directly in your server/LLM pipelines, the library exposes a fully decoupled, client-side approach.

### 1. How It Works
Your client application (React, Vue, Streamlit, vanilla HTML, etc.) renders its own buttons and message UI. To automatically capture feedback events without writing backend callback code, follow these simple conventions:

* **Markup Convention**: Wrap each assistant message or trace block in a DOM element containing the trace metadata:
  ```html
  <div data-trace-id="trace-123456" data-session-id="session-xyz" data-user-id="user-abc">
      <!-- Your Assistant message content -->
      <p>Here is your generated report...</p>
      
      <!-- Your custom feedback buttons -->
      <button class="thumb-up">👍</button>
      <button class="thumb-down">👎</button>
      <button class="copy-btn">Copy</button>
      <button class="retry-btn">Retry</button>
  </div>
  ```

* **Client JS Auto-Capture Script**: Include this lightweight browser event listener in your web frontend. It listens globally to user interaction events inside elements containing `data-trace-id` and forwards telemetry to the backend asynchronously:
  ```javascript
  (function() {
      if (window._smartllmops_autocapture_initialized) return;
      window._smartllmops_autocapture_initialized = true;

      function findMetaValue(container, attr) {
          if (!container) return null;
          return container.getAttribute(attr);
      }

      function sendFeedback(payload) {
          fetch("http://localhost:8000/feedback", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(payload)
          }).catch(err => console.error("Telemetry error:", err));
      }

      // Capture Copy events
      document.addEventListener("copy", function(e) {
          const selection = window.getSelection();
          if (!selection || selection.toString().trim() === "") return;
          const container = selection.anchorNode.parentNode.closest("[data-trace-id]");
          if (container) {
              sendFeedback({
                  trace_id: findMetaValue(container, "data-trace-id"),
                  session_id: findMetaValue(container, "data-session-id") || "session-unknown",
                  user_id: findMetaValue(container, "data-user-id") || "user-unknown",
                  output_copied: true
              });
          }
      });

      // Capture Click events
      document.addEventListener("click", function(e) {
          const container = e.target.closest("[data-trace-id]");
          if (!container) return;

          const text = (e.target.innerText || e.target.value || "").trim().toLowerCase();
          let payload = {
              trace_id: findMetaValue(container, "data-trace-id"),
              session_id: findMetaValue(container, "data-session-id") || "session-unknown",
              user_id: findMetaValue(container, "data-user-id") || "user-unknown"
          };

          if (text.includes("👍") || text === "up" || e.target.classList.contains("thumb-up")) {
              payload.thumb = "up";
          } else if (text.includes("👎") || text === "down" || e.target.classList.contains("thumb-down")) {
              payload.thumb = "down";
          } else if (text.includes("copy") || e.target.classList.contains("copy-btn")) {
              payload.output_copied = true;
          } else if (text.includes("retry") || e.target.classList.contains("retry-btn")) {
              payload.retry_clicked = true;
          } else {
              return; // Not a feedback element
          }

          sendFeedback(payload);
      });
  })();
  ```

### 2. Standard Streamlit Integration (Auto-Injected)
When running inside Streamlit, the SDK's `patch_streamlit()` automatically manages this entire lifecycle. It auto-injects the hidden metadata tags and the event listener JS script into Streamlit's virtual iframe, allowing you to use your standard custom Streamlit buttons seamlessly while capturing every feedback interaction!

