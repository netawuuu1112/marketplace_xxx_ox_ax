"""Per-task context, never inferred from user-supplied product text."""
from contextvars import ContextVar

user_id = ContextVar('llm_user_id',default=None)
observer = ContextVar('llm_usage_observer',default=None)


async def report(provider,model,kind,usage):
    callback=observer.get()
    if callback and usage:
        await callback(provider,model,kind,int(getattr(usage,'prompt_tokens',0) or 0),int(getattr(usage,'completion_tokens',0) or 0))
