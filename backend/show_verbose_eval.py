import asyncio, httpx, json

async def show_verbose():
    async with httpx.AsyncClient(base_url='http://localhost:8000', timeout=60) as c:
        r = await c.post('/api/auth/login', json={
            'employee_id':'EMP-007',
            'organisation_password':'Samanvaya@Org2024',
            'employee_password':'Samanvaya@Emp2024'
        })
        token = r.json()['token']
        h = {'Authorization': 'Bearer ' + token}

        # Run verbose evaluation for DEVELOPER
        r2 = await c.post('/api/evaluation/run', json={
            'employee_id': 'EMP-001',
            'start_date': '2026-09-01',
            'end_date': '2026-09-30',
            'period_label': '2026-09',
            'company_id': 'ORG-001',
            'skip_llm': True,
            'verbose': True
        }, headers=h, timeout=60)

        print('STATUS:', r2.status_code)
        if r2.status_code != 200:
            print('ERROR:', r2.text[:400])
            return

        ev = r2.json()

        print()
        print('=== EVALUATION SUMMARY ===')
        summary = ev.get('evaluation_summary', {})
        for k, v in summary.items():
            print(f'  {k}: {v}')

        print()
        print('=== PER-AGENT METRICS (verbose) ===')
        for dim, m in ev.get('agent_metrics', {}).items():
            agent_name = m.get('agent', dim)
            score = m.get('score')
            grade = m.get('grade')
            conf = m.get('confidence')
            risk = m.get('risk_level')
            print(f'  [{agent_name}]')
            print(f'    score      : {score}')
            print(f'    grade      : {grade}')
            print(f'    confidence : {conf}')
            print(f'    risk_level : {risk}')
            recs = m.get('recommendations') or []
            for rec in recs[:2]:
                print(f'    rec: {str(rec)[:80]}')
            summary_text = m.get('summary') or ''
            if summary_text:
                print(f'    summary: {summary_text[:100]}')
            print()

        print('=== FINAL SCORECARD ===')
        print(f'  employee_id   : {ev.get("employee_id")}')
        print(f'  employee_name : {ev.get("employee_name")}')
        print(f'  overall_score : {ev.get("overall_score")}')
        print(f'  final_score   : {ev.get("final_score")}')
        print(f'  grade         : {ev.get("grade")}')
        print(f'  confidence    : {ev.get("confidence")}')
        print(f'  latency_ms    : {ev.get("evaluation_latency_ms")}')
        print(f'  mode          : {ev.get("evaluation_summary", {}).get("evaluation_mode")}')
        print(f'  weights_used  : {ev.get("weights_used")}')

asyncio.run(show_verbose())
