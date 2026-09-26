import json,hashlib,shutil,collections,statistics
from pathlib import Path
from datetime import datetime
import eval_adbeta_jev as b
P=b.HERE/'exports';receipt=json.loads((P/'corrected-attack-run.json').read_text());run=Path(receipt['run_dir']);e=run/'eval';data=json.loads((run/'ADbeta1.0.json').read_text());source=json.loads((P/'beta1.0-20260923.json').read_text())
assert hashlib.sha256((run/'ADbeta1.0.json').read_bytes()).hexdigest()==receipt['dataset_sha256']
for a,c in zip(source['scenarios'],data['scenarios']):
 assert {k:v for k,v in c.items() if k!='questions'}=={k:v for k,v in a.items() if k!='questions'}
 for typ,rr in a['questions'].items():
  for orig,new in zip(rr,c['questions'][typ]):assert {k:v for k,v in new.items() if k!='adversarial'}==orig
rows=[json.loads(x) for x in (e/'results.jsonl').read_text().splitlines()];assert len(rows)==10556
clean={r['question_id']:r for r in rows if r['category']=='clean'};bykey={(r['question_id'],r['category']):r for r in rows};verified=0
for sc in data['scenarios']:
 for rr in sc['questions'].values():
  for rec in rr:
   entries=[('clean',rec['adversarial']['original_question_text'],sc['state'])]+[(s['id'],s['perturbed_question_text'],s['perturbed_state']) for s in rec['adversarial']['samples']]
   for cat,raw,state in entries:
    row=bykey[rec['question_id'],cat];resp=json.loads((e/'responses'/ (row['response_job_id']+'.json')).read_text())
    assert b.digest(b.request_bytes(state,[(row['item_id'],raw)]))==resp['body_sha256']
    _,ok,_=b.score(row,row['jev_answer']);assert ok==row['strict_correct'];verified+=1
summary=json.loads((e/'summary.json').read_text());token={}
for cat in summary['by_category']:
 rs=[r for r in rows if r['category']==cat];ds=[r['input_tokens']-clean[r['question_id']]['input_tokens'] for r in rs]
 token[cat]={'same':sum(x==0 for x in ds),'increased':sum(x>0 for x in ds),'decreased':sum(x<0 for x in ds),'median_difference':statistics.median(ds)}
summary['token_difference_by_category']=token
(e/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')

assert summary['complete'] and not summary['failed_or_missing']
repeat=[]
for qid,row in clean.items():
    rp=run/'clean-repeat'/'responses'/(row['response_job_id']+'.json')
    resp=json.loads(rp.read_text());assert resp['status']=='ok'
    original=json.loads((e/'responses'/(row['response_job_id']+'.json')).read_text())
    assert resp['body_sha256']==original['body_sha256']
    a=resp['answers'][row['item_id']];value,ok,_=b.score(row,a)
    repeat.append({'question_id':qid,'type':row['type'],'first_value':row['measured_value'],'second_value':value,'first_correct':row['strict_correct'],'second_correct':ok,'same_input_sha256':resp['body_sha256']})
def repeat_stats(rs):
    paired=[r for r in rs if r['first_correct']]
    return {'count':len(rs),'second_errors':sum(not r['second_correct'] for r in rs),'changed_values':sum(r['first_value']!=r['second_value'] for r in rs),'first_correct_count':len(paired),'correct_to_wrong':sum(not r['second_correct'] for r in paired),'wrong_to_correct':sum(r['second_correct'] and not r['first_correct'] for r in rs)}
summary['identical_input_repeat']={'overall':repeat_stats(repeat),'by_type':{t:repeat_stats([r for r in repeat if r['type']==t]) for t in ['noul','choice','score']}}
(e/'clean-repeat-results.json').write_text(json.dumps(repeat,ensure_ascii=False,indent=2)+'\n')
samplemap={}
for sc in data['scenarios']:
 for rr in sc['questions'].values():
  for rec in rr:
   for sample in rec['adversarial']['samples']:samplemap[rec['question_id'],sample['id']]=sample
methodstats={}
for cat in ['Q1','Q2']:
 methods=collections.defaultdict(list)
 for row in rows:
  if row['category']==cat:methods[samplemap[row['question_id'],cat]['method']].append(row)
 methodstats[cat]={}
 for method,rs in methods.items():
  paired=[r for r in rs if clean[r['question_id']]['strict_correct']]
  methodstats[cat][method]={'count':len(rs),'errors':sum(not r['strict_correct'] for r in rs),'baseline_correct':len(paired),'new_errors':sum(not r['strict_correct'] for r in paired)}
summary['query_method_results']=methodstats
summary['q1_method_eligibility']=dict(collections.Counter('|'.join(s['sampling']['eligible_methods']) for (qid,cat),s in samplemap.items() if cat=='Q1'))
summary['generation_methods']=data['summary']['methods']
(e/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
r=summary['identical_input_repeat']['overall']
top=sorted(summary['by_category'].items(),key=lambda kv:kv[1]['new_error_rate'],reverse=True)
text='\n## 修正与重复对照\n\n'
text+='唯一规范为本目录保存的 扰动生成prompt-en.md，SHA256：'+receipt['prompt_sha256']+'。未使用旧中文版规则。\n\n'
text+='Q1 按生成器可构造方法随机选择，Q2 使用实际词汇或句子改写，T3 加入场景对应的具体假设案例。所有方法从原题独立生成；这仍是程序辅助生成的候选集，并非人工逐题确认的攻击上限。\n\n'
text+=f"相同原题请求额外重复 {r['count']} 次，请求体哈希全部一致。第一次答对的 {r['first_correct_count']} 题中，重复调用有 {r['correct_to_wrong']} 题变错，另有 {r['wrong_to_correct']} 题由错变对；{r['changed_values']} 题输出值变化。不能机械相减得出净攻击成功率。\n\n"
text+='本轮条件新增错误率最高的三类：'+ '、'.join(f"{cat} {v['new_errors']}/{v['baseline_correct']}（{v['new_error_rate']:.2%}）" for cat,v in top[:3])+'。\n\n'
text+='S 类输入 token 变化只是暴露的间接证据；计数相同不能证明模型实际看到相同文本，也不能证明它成功识别了攻击。\n\n'
text+='Q1/Q2 分方法结果：\n```json\n'+json.dumps(methodstats,ensure_ascii=False,indent=2)+'\n```\n'
text+='重复原题按题型结果：\n```json\n'+json.dumps(summary['identical_input_repeat'],ensure_ascii=False,indent=2)+'\n```\n'
report=(e/'report.md').read_text().replace('每个输入本轮调用一次，统计的是这一轮结果；没有同输入重复基线，不能把所有微小数值变化归因于攻击。','每个对抗输入本轮调用一次，另有 812 个完全相同请求体的原题重复对照，结果见后文；仍不能把所有微小数值变化归因于攻击。')
(e/'report.md').write_text(report+text)
verification={'passed':True,'request_hashes_and_strict_scores_verified':verified,'identical_clean_repeat_request_hashes_verified':len(repeat),'original_records_and_label_provenance_unchanged':True,'unique_output_items':len(bykey),'failed_requests':len(summary['failed_or_missing']),'dataset_sha256':receipt['dataset_sha256'],'prompt_sha256':receipt['prompt_sha256']}
(e/'verification.json').write_text(json.dumps(verification,indent=2)+'\n')
backup=P/('ADbeta1.0-before-corrected-'+datetime.now().strftime('%Y%m%d-%H%M%S'));backup.mkdir()
for name in ['ADbeta1.0.json','ADbeta1.0-validation.json','ADbeta1.0-README.md']:
 if (P/name).exists():shutil.copy2(P/name,backup/name)
shutil.copy2(run/'ADbeta1.0.json',P/'ADbeta1.0.json');shutil.copy2(run/'validation.json',P/'ADbeta1.0-validation.json')
(P/'ADbeta1.0-README.md').write_text('# ADbeta1.0 修正版\n\n唯一规范：扰动生成prompt-en.md。全部 9,744 个候选从 beta1.0 重新生成，另调用 812 个原题及 812 次完全相同原题重复对照。Score 严格计分，候选独立语义审核 pending。\n\n完整快照、逐请求日志与结果：'+str(run)+'\n\n生成器 generate_corrected_attacks.py；评测器 eval_corrected_attacks.py；重复对照 eval_clean_repeat.py。原版已备份。\n')
print(json.dumps({'verification':verification,'repeat':summary['identical_input_repeat'],'query_methods':methodstats,'token':token,'categories':summary['by_category'],'backup':str(backup)},ensure_ascii=False))
