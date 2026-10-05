"""Anonymous shelf reports. No identity collection and no inventory mutations."""
import copy
from datetime import datetime, timezone
import hashlib
import json
import secrets
import time
from inventory import SAFE_ID, clean_text


def empty_reports():
    return dict(schemaVersion=1, revision=0, reports={}, operations={})


def validate_reports(doc):
    if (not isinstance(doc,dict) or doc.get('schemaVersion') != 1 or type(doc.get('revision')) is not int or
            doc['revision'] < 0 or not isinstance(doc.get('reports'),dict) or not isinstance(doc.get('operations'),dict)):
        raise ValueError('Invalid reports document.')
    for rid, report in doc['reports'].items():
        if not SAFE_ID.fullmatch(rid) or not isinstance(report,dict) or not SAFE_ID.fullmatch(str(report.get('shelfId',''))):
            raise ValueError('Invalid report identity.')
        if report.get('status') not in ('pending','resolved','dismissed') or not clean_text(report.get('text'),'Report',2000):
            raise ValueError('Invalid report content or status.')
        for key in ('binId','itemId'):
            if report.get(key) is not None and not SAFE_ID.fullmatch(str(report[key])):
                raise ValueError('Invalid report context.')
        for key in ('shelfLabel','binLabel','itemLabel','submittedAt','updatedAt'):
            clean_text(report.get(key,''),key,1000)
    for op, receipt in doc['operations'].items():
        if not SAFE_ID.fullmatch(op) or not isinstance(receipt,dict) or receipt.get('reportId') not in doc['reports']:
            raise ValueError('Invalid report receipt.')


def prepare_report(body, current, locations, inventory, attempts, client):
    if not isinstance(body,dict):
        raise ValueError('Invalid report.')
    operation=body.get('operationId')
    if not isinstance(operation,str) or not SAFE_ID.fullmatch(operation):
        raise ValueError('A unique submission ID is required.')
    description=clean_text(body.get('text'),'Report description',2000)
    if not description:
        raise ValueError('Describe what is incorrect (maximum 2,000 characters).')
    sid,bid,iid=body.get('shelfId'),body.get('binId'),body.get('itemId')
    for value in (sid,bid,iid):
        if value is not None and (not isinstance(value,str) or not SAFE_ID.fullmatch(value)):
            raise ValueError('Invalid report context.')
    fingerprint=hashlib.sha256(json.dumps([sid,bid,iid,description],ensure_ascii=False).encode()).hexdigest()
    if operation in current['operations']:
        receipt=current['operations'][operation]
        if receipt['fingerprint'] != fingerprint:
            raise ValueError('Submission ID already used. Start a new report.')
        return None,dict(submitted=True,reportId=receipt['reportId'])
    location=locations.get(sid)
    if not location or 'shelfMode' not in location or not location['mapped']:
        raise ValueError('This shelf is no longer mapped. Refresh the lab map before reporting.')
    if bid and sid+'/'+bid not in locations:
        raise ValueError('The selected bin is no longer available.')
    if iid and not any(stock['itemId']==iid and stock.get('shelfId')==sid and (not bid or stock.get('binId')==bid) for stock in inventory['stocks'].values()):
        raise ValueError('The selected item is no longer at this shelf.')
    now=time.time()
    recent=[value for value in attempts.get(client,[]) if value>now-3600]
    if sum(value>now-60 for value in recent)>=5 or len(recent)>=20:
        raise OverflowError('Too many reports. Please try again later.')
    attempts[client]=recent+[now]
    # A second operation ID for the same text/context shortly after a submission
    # is an accidental repeat, not another report.
    for rid, report in current['reports'].items():
        if report.get('fingerprint')==fingerprint and now-datetime.fromisoformat(report['submittedAt']).timestamp()<300:
            return None,dict(submitted=True,reportId=rid)
    doc=copy.deepcopy(current)
    rid='RP-'+secrets.token_hex(16)
    timestamp=datetime.now(timezone.utc).isoformat()
    doc['reports'][rid]=dict(shelfId=sid,binId=bid,itemId=iid,text=description,status='pending',
        shelfLabel=location['label'],binLabel=locations.get(sid+'/'+bid,{}).get('label','') if bid else '',
        itemLabel=inventory['items'].get(iid,{}).get('name',''),submittedAt=timestamp,updatedAt=timestamp,fingerprint=fingerprint)
    doc['operations'][operation]=dict(reportId=rid,fingerprint=fingerprint)
    doc['revision']+=1
    return doc,dict(submitted=True,reportId=rid)
