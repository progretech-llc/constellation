"""Read explicitly shared, reviewed activity documents through Hindsight's API."""
from __future__ import annotations

import ipaddress
import json
import os
import re
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

SHARED_TAGS = {'constellation:shared', 'structured-agent-activity'}
MAX_DOCUMENTS = 100
MAX_RESPONSE_BYTES = 2_000_000


def validate_source(source: dict) -> None:
    url = urlsplit(source.get('api_url', ''))
    if url.scheme not in {'http', 'https'} or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError('Hindsight API requires an HTTP(S) URL without credentials, query or fragment')
    try:
        loopback = ipaddress.ip_address(url.hostname).is_loopback
    except ValueError:
        loopback = url.hostname == 'localhost'
    if url.scheme == 'http' and not loopback:
        raise ValueError('Plain HTTP Hindsight API connections must use loopback')
    bank = source.get('bank_id')
    if not isinstance(bank, str) or not 1 <= len(bank) <= 512 or any(ord(c) < 32 for c in bank):
        raise ValueError('Configure one explicit Hindsight bank_id')
    key_env = source.get('api_key_env', '')
    if not isinstance(key_env, str) or (key_env and not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', key_env)):
        raise ValueError('api_key_env must name an environment variable, not contain a key')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _shared_tags(value: dict) -> bool:
    tags = value.get('tags')
    return isinstance(tags, list) and all(isinstance(tag, str) for tag in tags) and SHARED_TAGS.issubset(tags)


def _get(source: dict, suffix: str) -> dict:
    headers = {'Accept': 'application/json'}
    key_env = source.get('api_key_env')
    if key_env:
        key = os.environ.get(key_env)
        if not key:
            raise RuntimeError('Configured Hindsight API key environment variable is unset')
        headers['Authorization'] = 'Bearer ' + key
    request = Request(source['api_url'].rstrip('/') + suffix, headers=headers)
    with build_opener(NoRedirect).open(request, timeout=10) as response:
        data = response.read(MAX_RESPONSE_BYTES + 1)
    if len(data) > MAX_RESPONSE_BYTES:
        raise ValueError('Hindsight document response exceeds the size limit')
    return json.loads(data)


def read_shared_documents(source: dict) -> list[dict]:
    validate_source(source)
    base = '/v1/default/banks/' + quote(source['bank_id'], safe='') + '/documents'
    query = urlencode([('tags', tag) for tag in sorted(SHARED_TAGS)] +
                      [('tags_match', 'all_strict'), ('limit', str(MAX_DOCUMENTS)), ('offset', '0')])
    listing = _get(source, base + '?' + query)
    if not isinstance(listing, dict) or not isinstance(listing.get('items'), list):
        raise ValueError('Invalid Hindsight document listing')
    records = []
    for row in listing['items'][:MAX_DOCUMENTS]:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not _shared_tags(row):
            continue
        # Never fetch the content of entries not explicitly shared in the listing.
        doc = _get(source, base + '/' + quote(row['id'], safe=''))
        if not isinstance(doc, dict) or doc.get('id') != row['id'] or not _shared_tags(doc):
            continue
        try:
            record = json.loads(doc.get('original_text') or '')
        except (ValueError, TypeError):
            continue
        if not isinstance(record, dict) or record.get('scope') != 'project' or record.get('reviewed') is not True or record.get('provenance_type') != 'structured-agent-activity':
            continue
        if not isinstance(record.get('author'), str) or not record['author'] or not isinstance(record.get('project'), str):
            continue
        if not all(isinstance(record.get(field), list) and all(isinstance(v, str) for v in record[field]) for field in ('technical_steps', 'evidence')):
            continue
        records.append({**record, 'memory_id': row['id']})
    return records
