def patch_streamlit(tracer):
    try:
        import streamlit as st
        from streamlit.runtime.scriptrunner import get_script_run_ctx
    except ImportError:
        return

    # Prevent double patching
    if hasattr(st, "_smartllmops_patched"):
        return
    st._smartllmops_patched = True

    # 1. Patch st.chat_message context manager
    original_chat_message = st.chat_message

    class AssistantMessageContext:
        def __init__(self, original_ctx):
            self.original_ctx = original_ctx

        def __enter__(self):
            return self.original_ctx.__enter__()

        def __exit__(self, exc_type, exc_val, exc_tb):
            res = self.original_ctx.__exit__(exc_type, exc_val, exc_tb)
            
            try:
                ctx = get_script_run_ctx()
                run_id = ctx.script_requests.current_request_id if (ctx and ctx.script_requests) else "default"
                
                if "_smartllmops_render_counts" not in st.session_state:
                    st.session_state._smartllmops_render_counts = {}
                
                if run_id not in st.session_state._smartllmops_render_counts:
                    st.session_state._smartllmops_render_counts[run_id] = 0
                
                idx = st.session_state._smartllmops_render_counts[run_id]
                st.session_state._smartllmops_render_counts[run_id] += 1
                
                # Retrieve trace_id from stored history
                trace_list = st.session_state.get("_smartllmops_traces", [])
                if idx < len(trace_list):
                    trace_info = trace_list[idx]
                    tid = trace_info.get("trace_id")
                    session_id = trace_info.get("session_id") or st.session_state.get("session_id", "session-unknown")
                    user_id = trace_info.get("user_id") or st.session_state.get("user_id", "user-unknown")
                    
                    def send_feedback(thumb=None, retry_clicked=None, output_copied=None):
                        try:
                            # Log feedback asynchronously using our new public SDK method!
                            tracer.log_feedback(
                                trace_id=tid,
                                thumb=thumb,
                                retry_clicked=retry_clicked,
                                output_copied=output_copied,
                                session_id=session_id,
                                user_id=user_id
                            )
                        except Exception:
                            pass

                    # Inject hidden metadata so that the Javascript event auto-capture can associate events with the trace
                    st.markdown(
                        f'<div class="smartllmops-meta" data-trace-id="{tid}" data-session-id="{session_id}" data-user-id="{user_id}" style="display:none;"></div>',
                        unsafe_allow_html=True
                    )

                    # Inject the global JS auto-capture script if not already injected
                    if not st.session_state.get("_smartllmops_js_injected"):
                        st.components.v1.html(
                            """
                            <script>
                            (function() {
                                if (window.parent._smartllmops_autocapture_initialized) return;
                                window.parent._smartllmops_autocapture_initialized = true;

                                console.log("✅ SmartLLMOps: Client-side event auto-capture activated.");

                                function findMetaValue(container, attr) {
                                    if (!container) return null;
                                    const meta = container.querySelector('.smartllmops-meta');
                                    return meta ? meta.getAttribute(attr) : null;
                                }

                                function getTelemetryEndpoint() {
                                    return window.parent.SMART_LLMOPS_BACKEND_URL || "http://localhost:8000/feedback";
                                }

                                function sendFeedbackPayload(payload) {
                                    const url = getTelemetryEndpoint();
                                    window.parent.fetch(url, {
                                        method: 'POST',
                                        headers: {
                                            'Content-Type': 'application/json'
                                        },
                                        body: JSON.stringify(payload)
                                    })
                                    .then(res => {
                                        if (!res.ok) console.warn("SmartLLMOps: Failed to send feedback to backend:", res.statusText);
                                    })
                                    .catch(err => {
                                        console.error("SmartLLMOps: Feedback transmission error:", err);
                                    });
                                }

                                // 1. Capture copy events
                                window.parent.document.addEventListener('copy', function(e) {
                                    const selection = window.parent.getSelection();
                                    if (!selection || selection.toString().trim() === "") return;
                                    
                                    let anchor = selection.anchorNode;
                                    if (anchor && anchor.nodeType === Node.TEXT_NODE) {
                                        anchor = anchor.parentNode;
                                    }
                                    
                                    const chatMessage = anchor.closest('[data-testid="stChatMessage"]');
                                    if (chatMessage) {
                                        const traceId = findMetaValue(chatMessage, 'data-trace-id');
                                        if (traceId) {
                                            const sessionId = findMetaValue(chatMessage, 'data-session-id') || "session-unknown";
                                            const userId = findMetaValue(chatMessage, 'data-user-id') || "user-unknown";
                                            
                                            sendFeedbackPayload({
                                                trace_id: traceId,
                                                session_id: sessionId,
                                                user_id: userId,
                                                output_copied: true
                                            });
                                            console.log(`SmartLLMOps: Tracked COPY for trace ${traceId}`);
                                        }
                                    }
                                });

                                // 2. Capture click events (Thumbs Up, Thumbs Down, Copy, Retry)
                                window.parent.document.addEventListener('click', function(e) {
                                    const target = e.target;
                                    if (!target) return;

                                    const chatMessage = target.closest('[data-testid="stChatMessage"]');
                                    if (!chatMessage) return;

                                    const traceId = findMetaValue(chatMessage, 'data-trace-id');
                                    if (!traceId) return;

                                    const sessionId = findMetaValue(chatMessage, 'data-session-id') || "session-unknown";
                                    const userId = findMetaValue(chatMessage, 'data-user-id') || "user-unknown";

                                    const text = (target.innerText || target.value || "").trim().toLowerCase();
                                    
                                    let thumb = null;
                                    let retryClicked = null;
                                    let outputCopied = null;

                                    if (text.includes("👍") || text === "up" || text.includes("thumbs-up") || target.classList.contains("thumb-up") || target.id.includes("thumb-up")) {
                                        thumb = "up";
                                    } else if (text.includes("👎") || text === "down" || text.includes("thumbs-down") || target.classList.contains("thumb-down") || target.id.includes("thumb-down")) {
                                        thumb = "down";
                                    } else if (text.includes("copy") || text.includes("📋") || target.classList.contains("copy-btn") || target.id.includes("copy")) {
                                        outputCopied = true;
                                    } else if (text.includes("retry") || text.includes("🔄") || target.classList.contains("retry-btn") || target.id.includes("retry")) {
                                        retryClicked = true;
                                    }

                                    if (thumb || retryClicked || outputCopied) {
                                        sendFeedbackPayload({
                                            trace_id: traceId,
                                            session_id: sessionId,
                                            user_id: userId,
                                            thumb: thumb,
                                            retry_clicked: retryClicked,
                                            output_copied: outputCopied
                                        });
                                        console.log(`SmartLLMOps: Tracked click event for trace ${traceId}: thumb=${thumb}, retry=${retryClicked}, copy=${outputCopied}`);
                                    }
                                });
                            })();
                            </script>
                            """,
                            height=0,
                            width=0
                        )
                        st.session_state._smartllmops_js_injected = True
            except Exception:
                pass
            
            return res

    def patched_chat_message(name, *args, **kwargs):
        ctx = original_chat_message(name, *args, **kwargs)
        if name == "assistant":
            return AssistantMessageContext(ctx)
        return ctx

    st.chat_message = patched_chat_message

    # 2. Patch st.chat_input to replay retries
    original_chat_input = st.chat_input

    def patched_chat_input(*args, **kwargs):
        if "retry_prompt" in st.session_state and st.session_state.retry_prompt:
            return st.session_state.pop("retry_prompt")
        return original_chat_input(*args, **kwargs)

    st.chat_input = patched_chat_input
