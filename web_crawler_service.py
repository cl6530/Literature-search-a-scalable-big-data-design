import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

import json
import os
import re

from flask import Flask, request
from flask_restful import Resource, Api

import threading
from confluent_kafka import Producer, KafkaError

from minio import Minio

import pymongo
from werkzeug.wrappers import response

config = {
        'bootstrap.servers': 'localhost:9092',  # Replace with your Kafka broker(s)
        'client.id': 'my_producer',
        'acks': 'all'
    }

'''
This is a function to get all the links that contains the content of the txt books.
The max depth of link within link is 2, to retrieve all links, we check all link start with 'http://www.authorama.com/'
'''
def get_all_links(url, depth=0, max_depth=1):
    if depth > max_depth:
        return []

    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    links = []
    for link in soup.find_all('a'):
        href = link.get('href')
        absolute_url = urljoin(url, href)
        if absolute_url.startswith('http://www.authorama.com/'):
            links.append(absolute_url)
            nested_links = get_all_links(absolute_url, depth=depth+1, max_depth=max_depth)
            links.extend(nested_links)

    return links

def extract_chapter_number(url):
    base_name = os.path.basename(url)
    chapter_number = base_name.split('-')[-1].split('.')[0]
    return chapter_number

def get_book_details(book_url):
    response = requests.get(book_url)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    title_author = soup.title
    if title_author:
        title_author = title_author.string
        match = re.search(r'(.*)\s\(by\s(.*)\)', title_author)
        
        if match:
            title = match.group(1).strip()
            author = match.group(2).strip()
        else:
            title = title_author
            author = "Unknown"
    else:
        title = "Unknown"
        author = "Unknown"

    chapter = extract_chapter_number(book_url)

    content = []

    for paragraph in soup.find_all('p'):
        content.append(paragraph.text)

    book_details = {
        'title': title,
        'author': author,
        'chapter': chapter,
        'content': content
    }

    return book_details

def save_book_as_json(book_details, output_dir):
    filename = os.path.join(output_dir, book_details['title'].replace(' ', '_') + '_chapter_' + book_details['chapter'] + '.json')

    with open(filename, 'w', encoding='utf-8') as file:
        json.dump(book_details, file, ensure_ascii=False, indent=4)
        
    return filename

class MyPublisher(threading.Thread):
    def __init__(self, *args, **kwargs):
        print("MyPublisher init")
        super().__init__(*args, **kwargs)
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        print("MyPublisher run")
        
        # Create client of MinIO Storage
        client = Minio('localhost:9000', access_key='cl6530', secret_key='chenxiliu', secure=False)
        
        bucket = "books"
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
        
        # Connect to the MongoDB container
        mongo_client = pymongo.MongoClient('localhost', 27017)
        # Select the database
        mongo_db = mongo_client['books']
        # Select the collection
        mongo_collection = mongo_db['books_location']
        
        # Create Producer instance
        producer = Producer(config)

        # Optional per-message delivery callback (triggered by poll() or flush())
        # when a message has been successfully delivered or permanently
        # failed delivery (after retries).
        def delivery_callback(err, msg):
            if err:
                print('ERROR: Message failed delivery: {}'.format(err))
            else:
                print("Produced event to topic {topic}: key = {key:12} value = {value:12}".format(
                    topic=msg.topic(), key=msg.key().decode('utf-8'), value=msg.value().decode('utf-8')))
        
        url = 'http://www.authorama.com/'
        book_links = get_all_links(url)
        output_dir = '/tmp/books'
        topic = "books"
        count = 1
        for book_link in book_links:
            try:
                # Build the json file locally
                book_details = get_book_details(book_link)
                file_path = save_book_as_json(book_details, output_dir)
                
                object = "book" + str(count)
                # Upload book to MinIO storage
                result = client.fput_object(bucket, object, file_path) #file_path is local path, MinIO uses [bucket and object] to fetch files
                print(
                    "created {0} object; etag: {1}, version-id: {2}".format(
                        result.object_name, result.etag, result.version_id,
                    ),
                )
                
                # Insert book metadata to mongodb
                mongo_document = {
                    "id": count,
                    "title": book_details["title"],
                    "author": book_details["author"],
                    "chapter": book_details["chapter"],
                    "bucket": bucket, 
                    "object": object
                }
                mongo_result = mongo_collection.insert_one(mongo_document)
                print(f"mongo_id={mongo_result.inserted_id}")
                
                # Produce new message to kafka
                producer.produce(topic, str(count), str(count), callback=delivery_callback)
                
                count += 1
                print(f"count={count}")
                
                print("kafka produced")
            except:
                count += 1
                print(f"count={count}")
                print("Failed to process the new book.")
        
        # Block until the messages are sent.
        producer.poll(10000)
        producer.flush()
        
app = Flask(__name__)
api = Api(app)

# Create client of MinIO Storage
client_main = Minio('localhost:9000', access_key='cl6530', secret_key='chenxiliu', secure=False)

# Connect to the MongoDB container
mongo_main_client = pymongo.MongoClient('localhost', 27017)
# Select the database
mongo_main_db = mongo_main_client['books']
# Select the collection
mongo_main_collection = mongo_main_db['books_location']

class BookQuery(Resource):
    def get(self):
        print("enter BookQuery get")
        resp = []
        try:
            id = request.args.get('id')
            title = request.args.get('title')
            author = request.args.get('author')
            chapter = request.args.get('chapter')
            bucket = request.args.get('bucket')
            object = request.args.get('object')
            
            mongo_query = {}
            
            if id is not None:
                mongo_query["id"] = int(id)
                
            if title is not None:
                mongo_query["title"] = str(title)
                
            if author is not None:
                mongo_query["author"] = str(author)
                
            if chapter is not None:
                mongo_query["chapter"] = str(chapter)
                
            if bucket is not None:
                mongo_query["bucket"] = str(bucket)
                
            if object is not None:
                mongo_query["object"] = str(object)

            print(f"mongo_query={mongo_query}")
            
            cursor = mongo_main_collection.find(mongo_query)
            
            for document in cursor:
                client_main.fget_object(document["bucket"], document["object"], '/tmp/books/tmp.json')
                print('File downloaded')
                with open('/tmp/books/tmp.json', 'r') as f:
                    my_json = json.load(f)
                resp.append(my_json)
        except:
            print("Failed to query the new book.")
        
        return resp

class MongoQuery(Resource):
    def get(self):
        print("enter MongoQuery get")
        resp = []
        try:
            author = request.args.get('author')

            if author is None:
                return {}
            
            mongo_query = {"author": author}

            print(f"mongo_query={mongo_query}")
            
            cursor = mongo_main_collection.find(mongo_query)
            
            response = []
            for document in cursor:
                response.append(document)
        except:
            print("Failed to query the new book.")
        
        return resp

api.add_resource(BookQuery, '/query')
api.add_resource(MongoQuery, '/search')
    
if __name__ == '__main__':
    print("Start Web Crawler Service")
    producer_thread = MyPublisher()
    producer_thread.start()
    
    print("producer thread created")
    
    app.run(debug=False, port=8888)
    
    producer_thread.stop()
    producer_thread.join()