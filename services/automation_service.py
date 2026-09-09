"""
M-One WhatsApp Automation Service Facade (services/automation_service.py)
Re-exporta funções dos módulos coesos em services/automation/ para manter compatibilidade total.
"""

from services.automation.schema import (
    ensure_automation_schema,
    seed_default_flows_if_empty,
    acquire_contact_lock,
    release_contact_lock,
    record_node_effect,
    update_node_effect_status,
    reserve_wam_id_atomically
)

from services.automation.adapters import (
    send_meta_text_message,
    send_meta_media_message,
    send_meta_button_message,
    send_meta_list_message,
    AIProviderAdapterManager,
    execute_webhook_adapter
)

from services.automation.engine import (
    validate_input_format,
    find_active_matching_flow,
    get_active_session_for_contact,
    process_inbound_automation,
    start_new_flow_session,
    resume_session_with_input,
    get_next_node_id,
    execute_flow_step
)

from services.automation.workers import (
    process_pending_wams_worker,
    process_delays_worker,
    process_timeouts_worker,
    run_all_automation_workers
)

# Aliases de compatibilidade
process_pending_delayed_sessions = process_delays_worker
process_pending_timeouts = process_timeouts_worker
