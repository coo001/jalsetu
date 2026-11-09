import csv,json,time,datetime
from wq import post
ts=datetime.datetime.utcnow().isoformat()+'Z'; t0=time.time()
STID=int(__import__('sys').argv[1]); p='Total arsenic'; fy='2024-2025'
v=post('ContaminantwiseVillagefil',cpage=1,paraname=p,stid=STID,dtid=0,blid=0,gpid=0,villid=0,fy=fy)
vills=v['Contaminantwise']; tp=int(v.get('TotalPage') or 1)
for pg in range(2,tp+1):
    vills+=post('ContaminantwiseVillagefil',cpage=pg,paraname=p,stid=STID,dtid=0,blid=0,gpid=0,villid=0,fy=fy)['Contaminantwise']
print('villages',len(vills),flush=True)
samples=[];fails=[]
for i,x in enumerate(vills):
    try:
        s=post('Contaminantwisesamplefillist',cpage=1,paraname=p,stid=STID,dtid=x['DistrictId'],villid=x['VillageId'],fy=fy)['Contaminantwise']
    except Exception as e:
        fails.append({'village_id':x['VillageId'],'err':str(e)[:100]}); continue
    for y in s:
        samples.append({'param':p,'district':y['District'],'block':y['Block'],'gp':y['Grampanchayat'],'village':y['Village'],'village_id':x['VillageId'],'sample_id':y['SampleId'],'source':y['sample_sourceName'],'acceptable':y['Acceptablelimit'],'permissible':y['Permissiblelimit'],'value':y['Parametervalue'],'lab':y['labname'],'tested':y['s_report_approval_action_time']})
    if i%20==0: print(i,len(samples),flush=True)
out=f'wq6_BR_2024-2025_arsenic_samples.csv'
with open(out,'w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(samples[0].keys())); w.writeheader(); w.writerows(samples)
json.dump({'retrieved_utc':ts,'state_id':STID,'param':p,'fy':fy,'villages':len(vills),'samples':len(samples),'failed_villages':fails,'seconds':round(time.time()-t0,1)},open('br_arsenic_log.json','w'),indent=1)
print('done',len(samples),len(fails))
