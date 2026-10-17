"""Exercise the native API transport and explicit shared-document boundary."""
import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from hindsight_api import MAX_RESPONSE_BYTES, SHARED_TAGS, read_shared_documents, validate_source


class HindsightApiTests(unittest.TestCase):
    def setUp(self):
        self.requests = []
        self.record = {'scope':'project', 'reviewed':True,
                       'provenance_type':'structured-agent-activity',
                       'author':'codex', 'project':'Example',
                       'technical_steps':['Updated report'], 'evidence':['/tmp/report.md']}
        self.listing = {'items':[{'id':'private', 'tags':[]},
                                 {'id':'shared document', 'tags':sorted(SHARED_TAGS)}]}
        self.document = {'id':'shared document', 'tags':sorted(SHARED_TAGS),
                         'original_text':json.dumps(self.record)}
        self.redirect = False
        self.oversize = False
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                owner.requests.append((self.path, self.headers.get('Authorization')))
                if owner.redirect:
                    self.send_response(302)
                    self.send_header('Location', '/must-not-follow')
                    self.end_headers()
                    return
                value = owner.listing if urlsplit(self.path).query else owner.document
                data = b' ' * (MAX_RESPONSE_BYTES + 1) if owner.oversize else json.dumps(value).encode()
                self.send_response(200)
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.source = {'api_url':f'http://127.0.0.1:{self.server.server_port}',
                       'bank_id':'reviewed/shared', 'api_key_env':'CONSTELLATION_TEST_KEY'}
        self.env = patch.dict(os.environ, {'CONSTELLATION_TEST_KEY':'test-only-key'})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_reads_only_explicitly_shared_documents_from_one_configured_bank(self):
        result = read_shared_documents(self.source)
        self.assertEqual(result[0]['memory_id'], 'shared document')
        self.assertEqual(result[0]['author'], 'codex')
        query = parse_qs(urlsplit(self.requests[0][0]).query)
        self.assertEqual(set(query['tags']), SHARED_TAGS)
        self.assertEqual(query['tags_match'], ['all_strict'])
        self.assertEqual(query['limit'], ['100'])
        self.assertEqual(len(self.requests), 2)
        self.assertIn('/reviewed%2Fshared/documents/shared%20document', self.requests[1][0])
        self.assertTrue(all(auth == 'Bearer test-only-key' for _, auth in self.requests))
        self.assertFalse(any('/private' in path for path, _ in self.requests))

    def test_unreviewed_private_or_unstructured_content_is_not_rendered(self):
        for field, value in [('reviewed',False), ('scope','agent'),
                             ('provenance_type','chat'), ('evidence','not a list')]:
            with self.subTest(field=field):
                self.document['original_text'] = json.dumps({**self.record, field:value})
                self.assertEqual(read_shared_documents(self.source), [])

    def test_redirects_and_oversized_responses_fail_closed(self):
        self.redirect = True
        with self.assertRaises(HTTPError):
            read_shared_documents(self.source)
        self.assertEqual(len(self.requests), 1)
        self.redirect = False
        self.oversize = True
        with self.assertRaisesRegex(ValueError, 'size limit'):
            read_shared_documents(self.source)

    def test_remote_http_embedded_secrets_and_missing_bank_are_rejected(self):
        for change in [{'api_url':'http://example.com'},
                       {'api_url':'https://user:secret@example.com'},
                       {'api_url':'https://example.com?token=secret'}, {'bank_id':''},
                       {'api_key_env':'not an env variable'}]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_source({**self.source, **change})

    def test_ui_link_cannot_embed_credentials_or_launch_non_web_handlers(self):
        for value in ['file:///tmp/example', 'javascript:alert(1)', 'http://example.com',
                      'https://user:secret@example.com', 'https://example.com?token=secret']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_source({**self.source, 'ui_url': value})
        validate_source({**self.source, 'ui_url': 'http://127.0.0.1:9999'})
