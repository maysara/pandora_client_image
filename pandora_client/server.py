# encoding: utf-8
# vi:si:et:sw=4:sts=4:ts=4
import os
import json
import shutil
import time
import thread
from Queue import Queue
from threading import Thread

import ox
from twisted.web.resource import Resource
from twisted.web.static import File
from twisted.web.server import Site
from twisted.internet import reactor

import extract
from utils import hash_prefix

class UploadThread(Thread):
    def __init__(self, server):
        Thread.__init__(self)
        self.server = server

    def run(self):
        while True:
            oshash = self.server.upload.get()
            print oshash
            try:
                self.server.client.upload([oshash])
            except:
                print 'failed to upload', oshash
            self.server.upload.task_done()

class Server(Resource):

    def __init__(self, client):
        self.upload = Queue()
        self.client = client
        Resource.__init__(self)
        t = UploadThread(self)
        t.setDaemon(True)
        t.start()

    def active_encodes(self):
        conn, c = self.client._conn()
        site = self.client._config['url']
        active = int(time.mktime(time.localtime())) - 120
        status = 'active'
        sql = 'SELECT oshash FROM encode WHERE site = ? AND status = ? AND modified > ?'
        args = [site, status, active]
        c.execute(sql, tuple(args))
        files = [row[0] for row in c]
        #reset inactive encodes
        sql = 'UPDATE encode SET status = ? WHERE site = ? AND status = ? AND modified < ?'
        c.execute(sql, ('', site, 'active', active))
        conn.commit()
        return files

    def queued_encodes(self):
        site = self.client._config['url']
        files = self.client.get_encodes(site)
        return files

    def update_status(self, oshash, status):
        conn, c = self.client._conn()
        site = self.client._config['url']
        modified = int(time.mktime(time.localtime()))
        c.execute(u'UPDATE encode SET status = ?, modified = ? WHERE site = ? AND oshash = ?', (status, modified, site, oshash))
        conn.commit()

    def media_path(self, oshash):
        return os.path.join(
            self.client.media_cache(),
            os.path.join(*hash_prefix(oshash)),
            self.client.profile
        )

    def render_json(self, request, response):
        request.headers['Content-Type'] = 'application/json'
        return json.dumps(response, indent=2)

    def getChild(self, name, request):
        #make source media available via oshash
        if request.path.startswith('/get/'):
            oshash = request.path.split('/')[-1]
            for path in self.client.path(oshash):
                if os.path.exists(path):
                    f = File(path, 'application/octet-stream')
                    f.isLeaf = True
                    return f
        return self

    def render_PUT(self, request):
        if request.path.startswith('/upload'):
            parts = request.path.split('/')
            oshash = parts[-1]
            if len(oshash) == 16:
                path = self.media_path(oshash)
                ox.makedirs(os.path.dirname(path))
                with open(path, 'wb') as f:
                    shutil.copyfileobj(request.content, f)
                self.update_status(oshash, 'done')
                self.upload.put(oshash)
                return self.render_json(request, {
                    'path': path
                })
        request.setResponseCode(404)
        return '404 unkown location'

    def render_POST(self, request):
        if request.path.startswith('/status'):
            oshash = request.path.split('/')[-1]
            error = request.args['error']
            self.update_status(oshash, 'failed')
            return self.render_json(request, {})
        request.setResponseCode(404)
        return '404 unkown location'

    def render_GET(self, request):
        if request.path.startswith('/next'):
            response = {}
            files = self.queued_encodes()
            for oshash in files:
                path = self.media_path(oshash)
                if os.path.exists(path):
                    self.update_status(oshash, 'done')
                    self.upload.put(oshash)
                    continue
                info = self.client.info(oshash)
                if not info or 'error' in info:
                    continue
                for f in self.client.path(oshash):
                    if os.path.exists(f):
                        response['oshash'] = oshash
                        url = 'http://%s:%s/get/%s' % (request.host.host, request.host.port, oshash)
                        output = '/tmp/%s.%s' % (oshash, self.client.profile)
                        response['cmd'] = extract.video_cmd(url, output, self.client.profile, info)
                        response['cmd'][0] = 'ffmpeg'
                        response['output'] = output
                        self.update_status(oshash, 'active')
                        print oshash, f
                        return self.render_json(request, response)
            return self.render_json(request, response)
        elif request.path.startswith('/ping/'):
            parts = request.path.split('/')
            #FIXME: store client id somewhere
            client = parts[-1]
            oshash = parts[-2]
            self.update_status(oshash, 'active')
            return self.render_json(request, {})
        elif request.path.startswith('/update'):
            thread.start_new_thread(self.update, ())
            return self.render_json(request, {'status': True})
        elif request.path.startswith('/status'):
            return self.render_json(request, {
                'active': self.active_encodes(),
                'queue': self.queued_encodes()
            })
        request.headers['Content-Type'] = 'text/html'
        data = 'pandora_client distributed encoding server'
        return data

    def update(self):
        self.client.scan([])
        self.client.sync([])
        self.client.update_encodes(True)

def run(client):
    root = Server(client)
    site = Site(root)
    port = 8789
    interface = '0.0.0.0'
    reactor.listenTCP(port, site, interface=interface)
    print 'listening on http://%s:%s' % (interface, port)
    client.update_encodes()
    reactor.run()
