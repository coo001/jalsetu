import json,csv,time,re,html,urllib.parse,datetime
from wq import get,post,enc,op
ts=datetime.datetime.utcnow().isoformat()+'Z'
log={'retrieved_utc':ts}
for fy in ['2024-2025','2025-2026']:
    d=get('GetContaminantwiseData',cpage=1,st=0,dt=0,bl=0,gp=0,vill=0,fy=fy,IsPws=1,SchemeId=0,SampleType=0)
    rows=d['Contaminantwise']
    keys=['State','StateId','PH','TDS','Turbidity','Chloride','Total_Alkalinity','Total_Hardness','Sulphate','Iron','Total_Arsenic','Fluoride','Nitrate','Residual_Chlorine','Others','TotalColiform','TotalEcoil']
    with open(f'wq6_states_{fy}.csv','w',newline='') as f:
        w=csv.writer(f); w.writerow(keys); [w.writerow([r.get(k) for k in keys]) for r in rows]
    log[f'wq6_states_{fy}']={'states':len(rows),'villages_arsenic':sum(r['Total_Arsenic'] for r in rows),'villages_fluoride':sum(r['Fluoride'] for r in rows),'villages_nitrate':sum(r['Nitrate'] for r in rows),'villages_ecoli':sum(r['TotalEcoil'] for r in rows)}
    print(fy,log[f'wq6_states_{fy}'],flush=True)
params=['Fluoride','Nitrate','Total arsenic','Ecoil']
samples=[]; t0=time.time()
for p in params:
    v=post('ContaminantwiseVillagefil',cpage=1,paraname=p,stid=2,dtid=0,blid=0,gpid=0,villid=0,fy='2024-2025')
    vills=v['Contaminantwise']; tp=v.get('TotalPage') or 1
    for pg in range(2,int(tp)+1):
        vills+=post('ContaminantwiseVillagefil',cpage=pg,paraname=p,stid=2,dtid=0,blid=0,gpid=0,villid=0,fy='2024-2025')['Contaminantwise']
    for x in vills:
        s=post('Contaminantwisesamplefillist',cpage=1,paraname=p,stid=2,dtid=x['DistrictId'],villid=x['VillageId'],fy='2024-2025')['Contaminantwise']
        for y in s:
            samples.append({'param':p,'district':y['District'],'block':y['Block'],'gp':y['Grampanchayat'],'village':y['Village'],'village_id':x['VillageId'],'sample_id':y['SampleId'],'source':y['sample_sourceName'],'acceptable':y['Acceptablelimit'],'permissible':y['Permissiblelimit'],'value':y['Parametervalue'],'lab':y['labname'],'tested':y['s_report_approval_action_time']})
    log[f'AP_2024-25_{p}_villages']=len(vills); print(p,len(vills),len(samples),flush=True)
with open('wq6_AP_2024-2025_samples.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(samples[0].keys())); w.writeheader(); w.writerows(samples)
log['AP_samples']=len(samples); log['AP_sample_seconds']=round(time.time()-t0,1)
labs=[]
for page in range(1,8):
    q=urllib.parse.urlencode({'Parameter_id':enc(0),'TypeId':enc(0),'dt_Id':enc(0),'gpId':enc(0),'st_id':enc(2),'page':page})
    h=op.open('https://ejalshakti.gov.in/WQMIS/Main/lab_parameterlist?'+q,timeout=90).read().decode('utf-8','ignore')
    rows=[[' '.join(html.unescape(re.sub(r'<[^>]+>',' ',c)).split()) for c in re.findall(r'<td[^>]*>(.*?)</td>',r,re.S)] for r in re.findall(r'<tr[^>]*>(.*?)</tr>',h,re.S)]
    rows=[r for r in rows if len(r)>=9]
    names={l[1] for l in labs}; new=[r for r in rows if r[1] not in names]
    if not new: break
    labs+=new
with open('wq_labs_AP_L10.csv','w',newline='') as f:
    w=csv.writer(f); w.writerow(['sno','name','group','address','established','accredited','lat','lon','parameters']); w.writerows([r[:9] for r in labs])
log['AP_labs']=len(labs)
log['AP_labs_can_test']={k:sum(k.lower() in r[8].lower() for r in labs) for k in ['Fluoride','Nitrate','Arsenic','E. coli']}
json.dump(log,open('probe_log.json','w'),indent=1); print(json.dumps(log,indent=1))
