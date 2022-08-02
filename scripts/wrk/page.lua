-- wrk -c 10 -d 5 -t 5 --latency -s page.lua "http://localhost/api/v1/page"
wrk.method = "POST"
wrk.body = '{"type": "page", "properties": {"title": "Page One", "url": "http://localhost:8080/one", "pool_id": null, "width": 1680, "height": 619, "referrer": "http://localhost:8080/one", "zar": {"vid": {"id": "kgwevbe3.ryqmjkraheq", "t": 1604071692651, "origReferrer": "http://localhost:8080/one", "isNew": true, "visits": 1}}}, "options": {}, "userId": null, "anonymousId": "29d7dfba-47ed-4305-ad91-e0625101afbf", "meta": {"timestamp": 1604071694775}}'
wrk.headers["Content-Type"] = "application/json"
