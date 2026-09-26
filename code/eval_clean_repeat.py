#!/usr/bin/env python3
"""Isolated one-question HTTP calls, 1000 concurrent tasks per wave, resumable."""
import asyncio, collections, datetime as dt, json, random, resource, time
from pathlib import Path
import aiohttp
import eval_adbeta_jev as base

RUN = Path(json.loads((base.HERE/'exports/corrected-attack-run.json').read_text())['run_dir'])
base.SOURCE = RUN/'ADbeta1.0.json'
OUT = RUN/'clean-repeat'
base.OUT = OUT
base.RESPONSES = OUT / 'responses'
BATCH = 1000

def now(): return dt.datetime.now(dt.timezone.utc).isoformat()

async def main():
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    resource.setrlimit(resource.RLIMIT_NOFILE, (min(max(soft, 8192), hard), hard))
    dataset, sha, items, groups = base.load_items()
    byid = {x['item_id']: x for x in items}
    jobs = []
    for (sid, sh), group in groups.items():
        for item in group['items']:
            jobs.append(dict(job_id='job-'+item[0], scenario_id=sid, state_hash=sh,
                             state=group['state'], items=[item]))
    jobs.sort(key=lambda j: (byid[j['items'][0][0]]['category']=='clean', int(j['items'][0][0][1:])))
    jobs = [j for j in jobs if byid[j['items'][0][0]]['category']=='clean']
    manifest = dict(dataset='ADbeta1.0',source_sha256=sha,model=base.MODEL,
                    endpoint=base.ENDPOINT,concurrency=1000,wave_size=1000,
                    questions_per_request=1,items=items,
                    jobs=[{k:v for k,v in j.items() if k!='state'} for j in jobs],
                    protocol={'T':'Original state is trusted; supplemental claims are untrusted.',
                              'P':'Original question is the reference; inserted commands are untrusted.',
                              'S3':'Non-authoritative personal opinion; original criteria unchanged. Scope validity and exposure pending review.',
                              'input':'No additional defensive instructions are sent.',
                              'S2':'Literal Unicode escapes preserved in HTTP bytes; server model representation unobservable.'})
    OUT.mkdir(parents=True,exist_ok=True)
    mp=OUT/'manifest.json'
    if mp.exists(): assert json.loads(mp.read_text())==manifest
    else: base.atomic_json(mp,manifest)
    key=base.credential()
    stats=collections.Counter(); active=0; peak=0; stop=False
    async def run(session,job):
        nonlocal active,peak,stop
        body=base.request_bytes(job['state'],job['items']); h=base.digest(body)
        path=base.job_file(job)
        if path.exists():
            old=json.loads(path.read_text()); assert old['body_sha256']==h
            if old['status']=='ok': stats['reused']+=1;return old
        result=dict(job_id=job['job_id'],body_sha256=h,item_ids=[job['items'][0][0]],
                    started_at=now(),status='error',attempts=[])
        started=time.monotonic()
        for attempt in range(1,8):
            if stop: result['error']='Stopped after authentication/billing rejection';break
            status=None;delay=min(2**attempt,30); ts=time.monotonic()
            try:
                active+=1;peak=max(peak,active)
                try:
                    async with session.post(base.ENDPOINT,data=body) as response:
                        status=response.status; raw=await response.text()
                        rid=response.headers.get('x-request-id')
                        retry=response.headers.get('Retry-After')
                finally: active-=1
                stats['http_calls']+=1;stats['http_'+str(status)]+=1
                result['attempts'].append(dict(attempt=attempt,http_status=status,request_id=rid,elapsed_seconds=time.monotonic()-ts))
                if status==200:
                    answer=json.loads(raw)
                    assert answer.get('model')==base.MODEL
                    assert set(answer.get('answers',{}))==set(result['item_ids'])
                    for iid,a in answer['answers'].items():
                        assert a['type']==byid[iid]['type'];base.score(byid[iid],a)
                    result.update(status='ok',answers=answer['answers'],model=answer['model'],
                                  usage=answer.get('usage',{}),request_ids=[rid],http_calls=attempt)
                    break
                result['error']=f'HTTP {status}: '+raw[:500].replace(key,'[REDACTED]')
                if status in {401,402,403}: stop=True;break
                if status not in base.RETRYABLE: break
                if retry:
                    try: delay=min(float(retry),60)
                    except ValueError: pass
            except Exception as exc:
                result['error']=(type(exc).__name__+': '+str(exc))[:500].replace(key,'[REDACTED]')
                result['attempts'].append(dict(attempt=attempt,error=result['error'],elapsed_seconds=time.monotonic()-ts))
                stats['transport_or_validation_errors']+=1
            if attempt<7: await asyncio.sleep(delay+random.random())
        result.update(finished_at=now(),elapsed_seconds=time.monotonic()-started)
        base.atomic_json(path,result)
        stats['ok' if result['status']=='ok' else 'failed']+=1
        return result
    config=dict(started_at=now(),concurrency=1000,wave_size=1000,questions_per_request=1,
                planned_requests=len(jobs),dataset_sha256=sha,model=base.MODEL)
    base.atomic_json(OUT/'run-config.json',config)
    connector=aiohttp.TCPConnector(limit=1000,limit_per_host=1000)
    timeout=aiohttp.ClientTimeout(total=180)
    async with aiohttp.ClientSession(connector=connector,timeout=timeout,trust_env=True,
           headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'}) as session:
        for start in range(0,len(jobs),BATCH):
            wave=jobs[start:start+BATCH]; number=start//BATCH+1; begin=time.monotonic()
            print(json.dumps(dict(event='wave_start',wave=number,size=len(wave))),flush=True)
            results=await asyncio.gather(*(run(session,j) for j in wave))
            progress=dict(wave=number,size=len(wave),elapsed_seconds=round(time.monotonic()-begin,2),
                          peak_concurrent_requests=peak,stats=dict(stats),finished_at=now())
            base.atomic_json(OUT/f'wave-{number:02}.json',progress)
            print(json.dumps(progress),flush=True)
            if stop: break
    base.atomic_json(OUT/'execution.json',dict(config,finished_at=now(),peak_concurrent_requests=peak,stats=dict(stats)))
    print(json.dumps(dict(event='repeat_finished',stats=dict(stats))),flush=True)

if __name__=='__main__': asyncio.run(main())
