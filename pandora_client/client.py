# encoding: utf-8
# vi:si:et:sw=4:sts=4:ts=4
import os
import json
import subprocess
import time
import socket
import sys

import requests

import extract

class DistributedClient:

    def __init__(self, url, name):
        self.url = url
        self.name = name

    def ping(self, oshash):
        try:
            url = '%s/ping/%s/%s' % (self.url, oshash, self.name)
            requests.get(url)
        except:
            print 'cound not ping server'

    def status(self, oshash, status):
        url = '%s/status/%s' % (self.url, oshash)
        requests.post(url, {'error': status})
 
    def upload(self, oshash, path):
        url = '%s/upload/%s' % (self.url, oshash)
        with open(path) as f:
            requests.put(url, f)
   
    def next(self):
        url = '%s/next' % self.url
        r = requests.get(url)
        data = json.loads(r.content)
        if 'oshash' in data:
            self.encode(data['oshash'], data['cmd'], data['output'])
            return True
        return False

    def encode(self, oshash, cmd, output):
        cmd[0] = extract.command('ffmpeg')
        try:
            p = subprocess.Popen(cmd)
            r = None
            n = 0
            while True:
                r = p.poll()
                if r == None:
                    if n % 60 == 0:
                        self.ping(oshash)
                        n = 0
                    time.sleep(2)
                    n += 2
                else:
                    break
        except KeyboardInterrupt:
            p.kill()
            #encoding was stopped, put back in queue
            self.status(oshash, '')
            if os.path.exists(output):
                os.unlink(output)
            sys.exit(1)
        if r == 0:
            self.upload(oshash, output)
        else:
            self.status(oshash, 'failed')
        if os.path.exists(output):
            os.unlink(output)
    
    def run(self):
        new = True
        while True:
            if not self.next():
                if new:
                    new = False
                    print "currently no more files to encode, ctrl-c to quit"
                try:
                    time.sleep(60)
                except KeyboardInterrupt:
                    return
            else:
                new = True

if __name__ == '__main__':
    url = 'http://127.0.0.1:8789'
    if len(sys.args) == 0:
        name = socket.gethostname()
    else:
        name = sys.argv[1]
    c = DistributedClient(url, name)
    c.run()
