from parameters import JOB_POOL_SIZE, PORT, HOST
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS, cross_origin
from threading import Semaphore, Lock, Thread
from collections import namedtuple
import json
from ai import ALL_RESPONSES
import os

trusted_ip = []

Job = namedtuple('Job', ['doc', 'imageWorker', 'mode'])

class G:
    def __init__(self):
        self.conSem = Semaphore(JOB_POOL_SIZE)
        self.proSem = Semaphore(JOB_POOL_SIZE)
        self.jobsLock = Lock()
        for _ in range(JOB_POOL_SIZE):
            self.conSem.acquire()
        self.jobs = []

    def printJobs(self):
        print('jobs', ['I' if x.imageWorker.result is not None else '_' for x in self.jobs])

g = G()

from ai import recordResponse

app = Flask(__name__)
cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'

@app.route('/')
def index():
    with open('front/index.html', 'rb') as file:
        content = file.read()
    return content

@app.route('/scripts.js')
def scripts():
    with open('front/scripts.js', 'rb') as file:
        content = file.read()
    return content

@app.route('/styles.css')
def styles():
    with open('front/styles.css', 'rb') as file:
        content = file.read()
    return content

@app.route('/next')
def next_job():
    g.conSem.acquire()
    with g.jobsLock:
        for doc, imageWorker, mode in g.jobs:
            with imageWorker.lock:
                if imageWorker.result is not None:
                    _id = doc.id
                    _mode = mode
                    break
        else:
            return jsonify({'error': True})
    return jsonify({
        'doc_id': _id,
        'mode': _mode,
        'artists': doc.getArtists(),
        'tags': doc.getTags(),
    })

@app.route('/response')
def response():
    doc_id = request.args.get('doc_id')
    response = request.args.get('response')
    with g.jobsLock:
        for i, (doc, imageWorker, _) in enumerate(g.jobs):
            if doc.id == doc_id:
                break
        g.jobs.pop(i)
        g.printJobs()
    g.proSem.release()
    Thread(
        target=recordResponse,
        args=(response, doc, imageWorker.result),
    ).start()
    return 'ok'

@app.route('/img')
def image():
    doc_id = request.args.get('doc_id')
    with g.jobsLock:
        for doc, imageWorker, _ in g.jobs:
            if doc.id == doc_id:
                break
        else:
            return jsonify({'error': True})
    if imageWorker.result is None:
        return jsonify({'error': True})
    return imageWorker.result

@app.route('/add_to_blacklist', methods=['POST'])
def add_to_blacklist():
    tag = request.form.get('tag')
    with open('blacklist.txt', 'a') as file:
        file.write(tag + '\n')
    
    return jsonify({'message': 'Tag added to the blacklist.'})

def startServer_t():
    app.run(host=HOST, port=PORT)

def startServer():
    server_thread = Thread(target=startServer_t)
    server_thread.start()


