import asyncio
from types import SimpleNamespace
from llm.gateway import LLMGateway
from llm.usage import report,user_id


def test_parallel_usage_keeps_user_and_task_context():
    async def scenario():
        rows=[]
        class Pool:
            async def execute(self,sql,*args): rows.append(args)
        class Provider:
            async def complete(self,**kwargs):
                await asyncio.sleep(.001)
                await report('test','fixture-model',kwargs['kind'],SimpleNamespace(prompt_tokens=12,completion_tokens=8))
                return 'ok'
        gateway=LLMGateway.__new__(LLMGateway)
        gateway._db=SimpleNamespace(_pool=True,pool=Pool())
        async def call(uid,kind):
            token=user_id.set(uid)
            try: return await gateway._complete_tracked(Provider(),kind=kind)
            finally: user_id.reset(token)
        assert await asyncio.gather(call(1,'rank'),call(2,'review'))==['ok','ok']
        assert {(r[0],r[1]) for r in rows}=={(1,'rank'),(2,'review')}
        assert all(r[4:]==(12,8) for r in rows)
    asyncio.run(scenario())
