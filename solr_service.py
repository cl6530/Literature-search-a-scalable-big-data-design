from flask import Flask, request
from flask_restful import Resource, Api

import requests
import json

import threading
from confluent_kafka import Consumer, KafkaError

config = {
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'books_group',
    'auto.offset.reset': 'earliest'
}

class MyConsumer(threading.Thread):
    def __init__(self, *args, **kwargs):
        print("MyConsumer init")
        super().__init__(*args, **kwargs)
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        print("MyConsumer run")
        consumer = Consumer(config)
        consumer.subscribe(['books'])

        while not self._stop_event.is_set():
            try:
                msg = consumer.poll(1.0)  # Poll for up to 1 second for new messages
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        print(f"Reached end of partition {msg.topic()}/{msg.partition()}")
                    else:
                        print(f"Error while consuming message: {msg.error()}")
                else:
                    # Update the following lines to call web crawler service
                    print(f"Received message: {msg.value().decode('utf-8')}")
                    book_id = int(msg.value())
                    
                    web_svc_parms = {
                        "id": book_id
                    }
                    
                    web_svc_url = 'http://localhost:8888/query'
                    book = requests.get(web_svc_url, params=web_svc_parms).json()

                    print(json.dumps(book))

                    # uncomment after the crawler part is ready
                    # Set the Solr server URL and the core name
                    solr_url = "http://localhost:8983/solr"
                    core_name = "doc"

                    headers = {
                        "Content-Type": "application/json"
                    }

                    json_data = json.dumps(book[0])

                    response = requests.post(
                        f"{solr_url}/{core_name}/update/json/docs",
                        headers=headers,
                        data=json_data
                    )

                    # Print the HTTP response status code
                    print(response.status_code)

                    # Commit the changes to Solr
                    requests.get(f"{solr_url}/{core_name}/update?commit=true")

                    # Print the HTTP response status code
                    print(response.status_code)
            except:
                print("Failed to fetch message")

        consumer.close()

app = Flask(__name__)
api = Api(app)
    
class SolrQuery(Resource):
    def get(self):
        print("enter get")
        q = request.args.get('q')
        hl = request.args.get('hl')
        indent = request.args.get('indent')
        q_op = request.args.get('q.op')
        hl_fl = request.args.get('hl.fl')
        sort = request.args.get('sort')
        start = request.args.get('start')
        rows = request.args.get('rows')
        fq = request.args.get('fq')
        
        # Set the Solr server URL and the core name
        solr_url = "http://localhost:8983/solr"
        core_name = "doc"
        
        if q is None:
            return {}

        # Define the headers for the HTTP request
        headers = {
            "Content-Type": "application/json"
        }
        
        params = {"q": q}
        
        if hl is not None:
            params["hl"] = hl
            
        if indent is not None:
            params["indent"] = indent
            
        if indent is not None:
            params["q.op"] = q_op
            
        if hl_fl is not None:
            params["hl.fl"] = hl_fl
            
        if sort is not None:
            params["sort"] = sort
            
        if start is not None:
            params["start"] = start
            
        if rows is not None:
            params["rows"] = rows

        if fq is not None:
            params["fq"] = fq
            
        # add more params here, like fp
            
        print(f"params={params}")

        # Send the HTTP request to Solr
        response = requests.get(
            f"{solr_url}/{core_name}/select",
            headers=headers,
            params=params
        )

        # Parse the response JSON
        response_json = json.loads(response.content)
        
        return response_json

api.add_resource(SolrQuery, '/query')

if __name__ == '__main__':
    print("Start Solr Service")
    consumer_thread = MyConsumer()
    consumer_thread.start()
    
    print("thread created")
    
    app.run(debug=False, port=8887)
    
    consumer_thread.stop()
    consumer_thread.join()