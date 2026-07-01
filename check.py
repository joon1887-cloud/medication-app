import requests, re
r = requests.get(
    'https://apis.data.go.kr/1471000/DrugPrdtPrmsnInfoService07/getDrugPrdtPrmsnDtlInq06',
    params={'serviceKey':'bd7deeffc64e3900eacf5d3ce065ae9fc77345e59fdd29e54692c29e8ef2713e','item_name':'타이레놀','type':'json','numOfRows':1}
)
d = r.json()
nb = d['body']['items'][0].get('NB_DOC_DATA','')
articles = re.findall(r'ARTICLE[^>]*title="([^"]+)"', nb)
print('ARTICLE titles:', articles)
print()
print('NB 앞부분:', nb[:500])