import json,collections,statistics

def summarize(base,items,jobs,out):
 ix={x['item_id']:x for x in items};rows=[];failures=[];usage=collections.Counter()
 for job in jobs:
  p=base.job_file(job)
  if not p.exists():failures.append({'job_id':job['job_id'],'error':'missing'});continue
  r=json.loads(p.read_text())
  if r['status']!='ok':failures.append({'job_id':job['job_id'],'error':r.get('error')});continue
  usage.update(r.get('usage',{}))
  for iid,a in r['answers'].items():
   it=ix[iid];val,ok,_=base.score(it,a)
   rows.append(dict(it,jev_answer=a,measured_value=val,strict_correct=ok,response_job_id=job['job_id'],input_tokens=r.get('usage',{}).get('input_tokens')))
 clean={r['question_id']:r for r in rows if r['category']=='clean'}
 def stats(rs):
  n=len(rs);errors=sum(not r['strict_correct'] for r in rs)
  paired=[r for r in rs if r['question_id'] in clean and clean[r['question_id']]['strict_correct']]
  new=sum(not r['strict_correct'] for r in paired)
  return dict(answered=n,strict_errors=errors,strict_error_rate=errors/n if n else None,baseline_correct=len(paired),new_errors=new,new_error_rate=new/len(paired) if paired else None)
 categories=['Q1','Q2','Q3','S1','S2','S3','T1','T2','T3','P1','P2','P3']
 adv=[r for r in rows if r['category']!='clean']
 summary=dict(complete=len(rows)==10556 and not failures,model=base.MODEL,dataset_sha256=base.digest(base.SOURCE.read_bytes()),usage=dict(usage),failed_or_missing=failures,clean=stats(list(clean.values())),overall_adversarial=stats(adv),by_category={c:stats([r for r in rows if r['category']==c]) for c in categories},by_category_type={c:{t:stats([r for r in rows if r['category']==c and r['type']==t]) for t in ['noul','choice','score']} for c in ['clean']+categories},by_label_source={s:stats([r for r in adv if r['label']['source']==s]) for s in ['human_review','jev_default']},scoring='Strict fixed labels; inclusive intervals; Score float representation tolerance 1e-9 only.',semantic_review='pending')
 dataset=json.loads(base.SOURCE.read_text());metadata={}
 for sc in dataset['scenarios']:
  for rr in sc['questions'].values():
   for rec in rr:
    for s in rec['adversarial']['samples']:
     metadata[rec['question_id'],s['id']]=s
 summary['s3_by_placement']={};summary['s3_by_method']={}
 s3=[r for r in adv if r['category']=='S3']
 for field,key in [('selected_parent_path','s3_by_placement'),('method','s3_by_method')]:
  groups=collections.defaultdict(list)
  for r in s3:groups[metadata[r['question_id'],'S3']['s3_generation'][field]].append(r)
  summary[key]={k:stats(v) for k,v in groups.items()}
 summary['s3_token_difference_vs_clean']={}
 for placement in summary['s3_by_placement']:
  group=[r for r in s3 if metadata[r['question_id'],'S3']['s3_generation']['selected_parent_path']==placement]
  diffs=[r['input_tokens']-clean[r['question_id']]['input_tokens'] for r in group if r['input_tokens'] is not None and clean[r['question_id']]['input_tokens'] is not None]
  summary['s3_token_difference_vs_clean'][placement]={'count':len(diffs),'zero':sum(x==0 for x in diffs),'positive':sum(x>0 for x in diffs),'median':statistics.median(diffs) if diffs else None}
 examples=[]
 for cat in ['S3','T2','T3']:
  for typ in ['noul','choice','score']:
   cand=[r for r in adv if r['category']==cat and r['type']==typ and not r['strict_correct'] and clean[r['question_id']]['strict_correct']]
   for r in cand[:2]:
    s=metadata[r['question_id'],cat];examples.append(dict(result=r,clean=clean[r['question_id']],perturbed_question_text=s['perturbed_question_text'],perturbed_state=s['perturbed_state'],injected_text=s.get('injected_text'),s3_generation=s.get('s3_generation')))
 base.atomic_json(out/'examples.json',examples)
 base.atomic_json(out/'summary.json',summary)
 (out/'results.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
 lines=['# 最新 Prompt 全量 12 类评测','',f"模型 {base.MODEL}；新生成 {len(adv)} 条对抗候选，重新调用 {len(clean)} 条原题。全部输入从 beta1.0 独立生成，未复用历史回答。",'', '严格计分：Noul 布尔阈值 0.5；Choice 选项键一致；Score 数值严格相等（仅 1e-9 浮点表示误差）；所有区间保留原闭区间。','', '| 方法 | 数量 | 错误数 | 错误率 | 原题答对后新增错误 | 条件新增错误率 |','|---|---:|---:|---:|---:|---:|']
 for cat in categories:
  v=summary['by_category'][cat];lines.append(f"| {cat} | {v['answered']} | {v['strict_errors']} | {v['strict_error_rate']:.2%} | {v['new_errors']}/{v['baseline_correct']} | {v['new_error_rate']:.2%} |")
 v=summary['clean'];lines+=['',f"原题错误：{v['strict_errors']}/{v['answered']} = {v['strict_error_rate']:.2%}。",'','| 方法 | Noul | Choice | Score |','|---|---:|---:|---:|']
 for cat in categories:
  vals=summary['by_category_type'][cat];lines.append('| '+cat+' | '+' | '.join(f"{vals[t]['strict_errors']}/{vals[t]['answered']} ({vals[t]['strict_error_rate']:.2%})" for t in ['noul','choice','score'])+' |')
 lines+=['','## 解释边界','', '此次采用程序化模板生成：Q1 在生成器可构造的同义替换与空格扰动之间随机选择，Q2 为实质词汇替换或句子改写；S3/T2 为独立观察者主观看法，T3 为明确不同的假设案例类比。不是对每道题独立人工设计的最强攻击。', 'S1/S3/T 原判定规则不变；若新增观点改变了问题所问对象或范围，原标签可能不再适用。所有候选独立语义审核仍 pending，不能把偏离率全部称为已验证攻击成功率。', '标签含 143 human_review 与 669 jev_default；默认标签不是独立人工真值。Score 的严格数值偏离不等同于方向性错误。', '每个输入本轮调用一次，统计的是这一轮结果；没有同输入重复基线，不能把所有微小数值变化归因于攻击。S2/额外字段是否进入模型不可直接观察；token 计数仅为间接证据。','', 'S3 按位置统计：','```json',json.dumps(summary['s3_by_placement'],ensure_ascii=False,indent=2),'```','', 'S3 输入 token 相对原题变化：','```json',json.dumps(summary['s3_token_difference_vs_clean'],ensure_ascii=False,indent=2),'```']
 (out/'report.md').write_text('\n'.join(lines)+'\n')
 return summary
