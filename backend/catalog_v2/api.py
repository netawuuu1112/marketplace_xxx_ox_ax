"""Versioned API; all ownership comes from the existing server-side authenticator."""
from functools import wraps
from aiohttp import web
from pydantic import ValidationError
from .models import SearchRequest
from .service import get_service


def register_routes(app, context_key, resolve_user, require_admin):
    def db(request): return request.app[context_key].db
    def service(request): return get_service(db(request))

    def endpoint(function):
        @wraps(function)
        async def guarded(request):
            user=resolve_user(request)
            try:
                result=await function(request,user)
                if isinstance(result,web.StreamResponse): return result
                if hasattr(result,'model_dump'): result=result.model_dump(mode='json')
                return web.json_response(result)
            except ValidationError:
                return web.json_response({'detail':'Некорректные параметры запроса'},status=400)
            except ValueError as exc:
                return web.json_response({'detail':str(exc)[:250]},status=400)
            except LookupError:
                raise web.HTTPNotFound(text='Объект не найден')
            except RuntimeError as exc:
                raise web.HTTPTooManyRequests(text=str(exc)[:250])
        return guarded

    @endpoint
    async def start(request,user):
        payload=SearchRequest.model_validate(await request.json())
        result=await service(request).start(user,payload)
        return web.json_response(result.model_dump(mode='json'),status=202)

    @endpoint
    async def state(request,user):
        result=await service(request).snapshot(user,request.match_info['search_id'])
        limit=min(100,max(1,int(request.query.get('limit','50'))))
        offset=max(0,int(request.query.get('offset','0')))
        data=result.model_dump(mode='json')
        data['total_groups']=len(data['groups'])
        data['groups']=data['groups'][offset:offset+limit]
        data['related']=data['related'][offset:offset+limit]
        return data

    @endpoint
    async def cancel(request,user):
        await service(request).cancel(user,request.match_info['search_id'])
        return {'ok':True}

    @endpoint
    async def product(request,user):
        group=await service(request).get_product(user,request.match_info['product_id'])
        return {'offers':[o.model_dump(mode='json') for o in group.offers]} if request.path.endswith('/offers') else group

    @endpoint
    async def recent(request,user):
        return await service(request).repository.recent(user)

    @endpoint
    async def profile(request,user):
        value=None
        if request.method=='PATCH':
            value=(await request.json()).get('region')
            if not isinstance(value,str) or len(value)>100: raise ValueError('Некорректный регион')
            value=value.strip()
        return {'region':await service(request).repository.region(user,value)}

    @endpoint
    async def favorites(request,user):
        repo=service(request).repository
        if request.method=='GET':
            return {'products':[g.model_dump(mode='json') for g in await repo.list_favorites(user)]}
        pid=request.match_info.get('product_id') or (await request.json()).get('product_id')
        if not isinstance(pid,str) or len(pid)>200: raise ValueError('Выберите товар')
        await repo.favorite(user,pid,remove=request.method=='DELETE')
        return {'ok':True}

    def monitor_db(request):
        instance=db(request)
        if not hasattr(instance,'pool'): raise web.HTTPServiceUnavailable(text='Мониторинг требует PostgreSQL')
        return instance

    @endpoint
    async def watches(request,user):
        from .watches import WatchCreate,create_watch,list_watches
        instance=monitor_db(request)
        if request.method=='GET': return {'watches':await list_watches(instance,user)}
        payload=WatchCreate.model_validate(await request.json())
        result=await create_watch(instance,user,payload)
        return web.json_response(result,status=201)

    @endpoint
    async def edit_watch(request,user):
        from .watches import WatchPatch,update_watch,delete_watch
        instance=monitor_db(request); wid=int(request.match_info['watch_id'])
        if request.method=='DELETE':
            if not await delete_watch(instance,user,wid): raise LookupError()
            return {'ok':True}
        result=await update_watch(instance,user,wid,WatchPatch.model_validate(await request.json()))
        if result is None: raise LookupError()
        return result

    @endpoint
    async def history(request,user):
        from .watches import history as load_history
        pid=request.match_info['product_id']
        await service(request).get_product(user,pid)
        days=request.query.get('days','30')
        if days not in ('7','30','90','all'): raise ValueError('Неизвестный период')
        result=await load_history(monitor_db(request),user,pid,days)
        if not result['points']:
            result=await service(request).repository.history(user,pid,days)
        return result

    @endpoint
    async def notifications(request,user):
        from .watches import notifications as load_notifications
        return {'notifications':await load_notifications(monitor_db(request),user)}

    @endpoint
    async def usage(request,user):
        await require_admin(request)
        rows=await monitor_db(request).pool.fetch("SELECT user_id,task,provider,model,sum(input_tokens) AS input_tokens,sum(output_tokens) AS output_tokens,count(*) AS calls FROM mf_llm_usage WHERE created_at>now()-interval '30 days' GROUP BY user_id,task,provider,model LIMIT 500")
        return {'usage':[dict(row) for row in rows]}

    for method,path,handler in [
        ('POST','/search',start),('GET','/search/{search_id}',state),('DELETE','/search/{search_id}',cancel),
        ('GET','/products/{product_id}',product),('GET','/products/{product_id}/offers',product),('GET','/products/{product_id}/history',history),
        ('GET','/recent',recent),('GET','/profile',profile),('PATCH','/profile',profile),
        ('GET','/favorites',favorites),('POST','/favorites',favorites),('DELETE','/favorites/{product_id}',favorites),
        ('GET','/watches',watches),('POST','/watches',watches),('PATCH',r'/watches/{watch_id:-?\d+}',edit_watch),('DELETE',r'/watches/{watch_id:-?\d+}',edit_watch),
        ('GET','/notifications',notifications),('GET','/admin/usage',usage)]:
        app.router.add_route(method,'/api/v2'+path,handler)

    async def shutdown(application):
        instance=getattr(application[context_key].db,'_catalog_v2_service',None)
        if instance: await instance.close()
    app.on_cleanup.append(shutdown)
