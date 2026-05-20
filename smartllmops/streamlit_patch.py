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

                    # small horizontal row for interactions
                    col1, col2, col3, col4, col5 = st.columns([0.08, 0.08, 0.15, 0.15, 0.54])
                    with col1:
                        if st.button("👍", key=f"smart_up_{tid}_{idx}"):
                            send_feedback(thumb="up")
                            st.toast("Feedback sent! Thank you.")
                    with col2:
                        if st.button("👎", key=f"smart_down_{tid}_{idx}"):
                            send_feedback(thumb="down")
                            st.toast("Feedback sent! Thank you.")
                    with col3:
                        if st.button("📋 Copy", key=f"smart_copy_{tid}_{idx}"):
                            send_feedback(output_copied=True)
                            st.toast("Copy event tracked!")
                    with col4:
                        if st.button("🔄 Retry", key=f"smart_retry_{tid}_{idx}"):
                            send_feedback(retry_clicked=True)
                            st.toast("Retry tracked!")
                            
                            # Find the matching preceding user prompt in st.session_state.messages
                            if "messages" in st.session_state and isinstance(st.session_state.messages, list):
                                assis_count = 0
                                for m_idx, msg in enumerate(st.session_state.messages):
                                    if msg.get("role") == "assistant":
                                        if assis_count == idx:
                                            if m_idx > 0 and st.session_state.messages[m_idx - 1].get("role") == "user":
                                                st.session_state.retry_prompt = st.session_state.messages[m_idx - 1]["content"]
                                                st.rerun()
                                            break
                                        assis_count += 1
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
