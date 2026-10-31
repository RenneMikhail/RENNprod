"""Server-side projections. Free text is restricted because it may contain PII/prices."""
import json
import auth

def specialist(row, actor):
    if auth.allowed(actor, '*'): return row
    result={k:row[k] for k in ('id','name','verified','created_at') if k in row}
    profile=row['profile']
    result['profile']={k:profile[k] for k in ('city','roles','skills','tasks','mobility','equipment','languages','timezone','portfolio','portfolio_role') if k in profile}
    for permission, keys in [('contacts:read',('email','phone','telegram','contact_verified')),('finances:read',('rate','currency'))]:
        if auth.allowed(actor,permission):
            result['profile'].update({k:profile[k] for k in keys if k in profile})
    if auth.allowed(actor,'contacts:read'): result['telegram_id']=row.get('telegram_id')
    return result

def intake(row,actor):
    payload=json.loads(row['payload'])
    if not (auth.allowed(actor,'contacts:read') and auth.allowed(actor,'finances:read')):
        keys=['kind','source','service','locale','city','test']
        if auth.allowed(actor,'contacts:read'): keys+=['contact','name']
        payload={k:payload[k] for k in keys if k in payload}
    return {**row,'payload':json.dumps(payload,ensure_ascii=False)}

def state(data,actor):
    if auth.allowed(actor,'*'): return data
    data['specialist']=[specialist(r,actor) for r in data['specialist']]
    data['intake']=[intake(r,actor) for r in data['intake']]
    # Arbitrary briefs and offer terms can contain both contact and finance data.
    unrestricted=auth.allowed(actor,'contacts:read') and auth.allowed(actor,'finances:read')
    if not unrestricted:
        for row in data['orders']: row['brief']='{}'
        for row in data['offer']: row['terms']='{}'
    if not auth.allowed(actor,'finances:read'):
        for row in data['role_slot']: row.pop('budget',None)
    return data


def workspace(data, actor):
    if actor['role']=='manager' and not (auth.allowed(actor,'contacts:read') and auth.allowed(actor,'finances:read')):
        data['brief']={}
        data['discussion']=[]
    return data
