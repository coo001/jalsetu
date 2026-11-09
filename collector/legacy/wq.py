import base64,json,sys,urllib.parse,urllib.request,http.cookiejar
from cryptography.hazmat.primitives.ciphers import Cipher,algorithms,modes
from cryptography.hazmat.primitives import padding
K=b'8080808080808080'
def enc(v):
    p=padding.PKCS7(128).padder(); d=p.update(str(v).encode())+p.finalize()
    e=Cipher(algorithms.AES(K),modes.CBC(K)).encryptor(); return base64.b64encode(e.update(d)+e.finalize()).decode()
cj=http.cookiejar.CookieJar(); op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
op.addheaders=[('User-Agent','Mozilla/5.0'),('X-Requested-With','XMLHttpRequest')]
op.open('https://ejalshakti.gov.in/WQMIS/Report/Contaminantwise',timeout=60).read()
def get(path,**kw):
    q=urllib.parse.urlencode({k:enc(v) for k,v in kw.items()})
    r=op.open(f'https://ejalshakti.gov.in/WQMIS/Report/{path}?{q}',timeout=90).read()
    return json.loads(r)
if __name__=='__main__':
    d=get('GetContaminantwiseData',cpage=1,st=0,dt=0,bl=0,gp=0,vill=0,fy='2024-2025',IsPws=1,SchemeId=0,SampleType=0)
    print(list(d.keys())); rows=d['Contaminantwise']; print(len(rows)); print(json.dumps(rows[:2])[:1500])

def post(path,**kw):
    import time
    for i in range(4):  # retry
        try:
            return _post(path,**kw)
        except Exception as e:
            if i==3: raise
            time.sleep(5*(i+1))
def _post(path,**kw):
    data=urllib.parse.urlencode({k:enc(v) for k,v in kw.items()}).encode()
    r=op.open(f'https://ejalshakti.gov.in/WQMIS/Report/{path}/',data=data,timeout=90).read()
    return json.loads(r)
