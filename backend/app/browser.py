import socket,ipaddress
from urllib.parse import urlparse
from playwright.async_api import async_playwright
from app.config import settings
sessions={}
def validate(url):
 p=urlparse(url)
 if p.scheme not in ('http','https') or not p.hostname:raise ValueError('Enter a valid http/https URL')
 if p.hostname in ('localhost',) or p.hostname.endswith('.local'):raise ValueError('Local destinations are blocked')
 try:
  for a in socket.getaddrinfo(p.hostname,None):
   ip=ipaddress.ip_address(a[4][0])
   if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:raise ValueError('Private/internal network URL blocked')
 except socket.gaierror:raise ValueError('Hostname could not be resolved')
 return url
async def inspect(sid,url):
 validate(url);pw=await async_playwright().start();b=await pw.chromium.launch(headless=settings.browser_headless);ctx=await b.new_context();page=await ctx.new_page();await page.goto(url,wait_until='domcontentloaded',timeout=60000);await page.wait_for_timeout(1000)
 fields=await page.locator('input:not([type=hidden]),textarea,select,button').evaluate_all("""es=>es.filter(e=>{let r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'}).map((e,index)=>({index,tag:e.tagName.toLowerCase(),type:e.type||'',name:e.name||'',label:([...e.labels||[]].map(x=>x.innerText).join(' ')||e.closest('label')?.innerText||e.getAttribute('aria-label')||e.placeholder||e.name||'').trim(),placeholder:e.placeholder||'',required:!!e.required,options:e.tagName==='SELECT'?[...e.options].map(o=>o.text):[]}))""")
 sessions[sid]={'pw':pw,'browser':b,'context':ctx,'page':page}
 return {'title':await page.title(),'url':page.url,'fields':fields[:100]}
async def fill(sid,items):
 page=sessions[sid]['page'];out=[]
 for x in items:
  try:
   loc=page.locator('input:not([type=hidden]):visible,textarea:visible,select:visible,button:visible').nth(x['index']);tag=await loc.evaluate('(e)=>e.tagName.toLowerCase()');typ=await loc.get_attribute('type') or ''
   if tag=='select':await loc.select_option(label=str(x['value']))
   elif tag=='button' or typ in ('submit','button','file','checkbox','radio','password'):raise ValueError('manual control')
   else:await loc.fill(str(x['value']))
   out.append({'index':x['index'],'status':'filled'})
  except Exception as e:out.append({'index':x['index'],'status':'manual','reason':type(e).__name__})
 return out
async def enter_answer(sid,index,value):
 p=sessions[sid]['page'];loc=p.locator('input:not([type=hidden]):visible,textarea:visible,select:visible,button:visible').nth(index)
 if await loc.evaluate('(e)=>e.tagName.toLowerCase()')=='select':await loc.select_option(label=value)
 else:await loc.fill(value)
async def submit(sid):
 p=sessions[sid]['page'];loc=p.locator('button[type=submit],input[type=submit]')
 if await loc.count()==0:loc=p.get_by_role('button',name=__import__('re').compile('submit|apply now',__import__('re').I))
 if await loc.count()==0:raise RuntimeError('Submit button not confidently identified; submit manually')
 await loc.first.click();await p.wait_for_timeout(1300);return {'url':p.url,'title':await p.title(),'text':(await p.locator('body').inner_text())[:2000]}
