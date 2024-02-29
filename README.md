# Literature search, a scalable big data design
## 1. Introduction
  As the volume of published literary texts continues to increase rapidly, it has become increasingly difficult to locate specific contents in a timely manner. To address this issue, a literature search engine focused on specific literature sources could facilitate quick and efficient retrieval of desired texts. By inputting paragraphs, quotes, or even individual words, such a search engine could be used to search publicly available patent literature and identify related works. 

  We aim to create a keyword and phrase search system based on literary masterpieces, allowing users to enter any word or phrase and receive a list of books containing those words. This work proposes a solution on processing enormous amounts of texts that could be a fundamental component of a library management system. Thus this design will be a scalable solution for larger-scale applications in the future.

  Our design is a real Big Data problem:
Big volume: As our design aims to deal with large Volume that It involves processing and analyzing a massive volume of published literary texts, including books, articles, and patent literature, which grows rapidly over time.
Velocity: As new literature is published and added to the database, our design aims to be able to handle the continuous influx of data and provide real-time or near-real-time search results to users.
Veracity: Our design also aims to ensure the accuracy and reliability of search results for a successful big data project. This means the search engine must be able to distinguish between relevant and irrelevant content, as well as handle potential issues such as misspellings, synonyms
Scalability: The design of the project must be able to accommodate the growing volume of data and user requests without significant degradation in performance. This requires a scalable architecture that can handle large-scale applications in the future.
Variety: our design also aims to deal with variety that our objects are a wide variety of data types coming from diverse sources
Value: Importantly, our project aims to provide a valuable service to users by enabling them to quickly and efficiently locate specific content in a vast pool of information. This can save time and resources for researchers, students, and other users who need to find relevant literature.

## 2. Architecture design
### 2.1  Architecture
  To accommodate the above requirements, we have an architecture design like this shown in Figure 1. We developed a web crawler service for crawling the contents from the target website, save contents to our distributed file storage system, and save metadata to mongoDB. We initially designed to use hadoop HDFS, however, we met some difficulties setting up the docker environment with hadoop HDFS, we considered using Amazon S3 instead, but it cannot be put into a docker container, and finally we found that MinIO is an excellent alternative for hadoop HDFS. MinIO is an open-source object storage server that is compatible with Amazon S3 APIs, and can be used to store and retrieve unstructured data such as images, videos, log files, backups, and other files. 

  MongoDB is a popular open-source document-oriented NoSQL database management system. It is designed to scale horizontally, meaning it can handle large amounts of data and high traffic loads by distributing data across multiple servers or nodes in a cluster. This allows for high availability and performance. MongoDB has flexible Schema, and is able to do querying and indexing. MongoDB provides a powerful query language that supports a wide range of query types, including filtering, sorting, and aggregation. It also supports indexing to improve query performance.

  We then have a SOLR service responsible for query purposes,  saving and retrieving information from SOLR cloud. SOLR cloud is an open-source search platform that is used to index, search, and analyze large volumes of data. SOLR is designed to be highly scalable, performant, and provide fast, relevant search results. It supports features such as full-text search, faceted search, geospatial search, and relevance ranking, which can be used to build powerful search applications. Overall, SOLR is a powerful and flexible search platform that can be used in a wide range of applications and environments.

  We use Kafka and REST API to communicate with the crawler service and SOLR service, and we developed a web application for users to interact with the searching system. Kafka is an open-source distributed streaming platform. It is designed to handle high-volume, real-time data streams efficiently and reliably. Kafka provides a messaging system that allows applications and systems to publish, subscribe, and process streams of records. Kafka is designed to handle high data throughput and large-scale deployments. It can horizontally scale by adding more brokers to a cluster and distributing the load across them. 

![Figure 1. Design of the literature search system architecture](https://github.com/cl6530/literature-search-big-data/blob/main/figures/BigDataProjectArchitecture.jpg)Figure 1. Design of the literature search system architecture

### 2.2 Strength of the architecture
  To be a good architecture design, the system needs to have good scalability, extensibility, maintainability, and be highly resilient. In our system, we choose scalable components such as MinIO, Kafka, MongoDB and SOLR cloud to make the whole system scalable. We modularize the service to make the system easily extensible for future larger-scale applications. We make both crawler service and SOLR service microservices for better maintainability since each service only interacts with its own databases, there is no coupling between two services. The search based on SOLR cloud is also fault tolerant, the MinIO, Kafka, MongoDB and SOLR all have features of sharding and replicas, these all make the system very resilient. 

  All web services need synchronous communication in our case is the restAPI, but from the aspect of scaling the project, we need kafka to process large throughput more robustly and stably. That is why we need both communication technologies. 
##3.	Implementation and analysis of each service
###3.1 Start the system
Set up:
Run docker-compose.yaml
```bash
docker-compose up -d
```

Create kafka topic in kafka’s container:
```bash
docker exec -it brokernew /bin/bash
kafka-topics --create --topic books --partitions 1 --replication-factor 1 --if-not-exists --bootstrap-server localhost:9092
kafka-topics --list --bootstrap-server localhost:9092
```

Create SOLR collection (‘doc’ in our case) in SOLR’s container
```bash
docker exec -it solrnew /bin/bash
solr create -c doc
```

Run 3 python files
```python
#pip install flask flask_restful confluent_kafka beautifulsoup4 pymongo minio
python web_app.py
python web_cralwer_service.py
python solr_service.py

http://localhost:8886/
```
To check Mongo:
```bash
docker exec -it mongodbnew mongosh
show dbs
```


How it works:
Web crawler will automatically crawl the website and store the books in MinIO, metadata in mongoDB. It also produces a message to kafka to notify SOLR service that a new book has been fetched. Solr service will consume the kafka message and upload it into SOLR. Web UI will call web crawler service and SOLR service to search. Exact search uses web crawler service and search everything uses SOLR service.
###3.2 Web Crawler service implementation
The crawler stores the book details as JSON files and uploads them to MinIO object storage. Metadata about the book is stored in a MongoDB instance, and a message is sent to a Kafka topic each time a new book is processed. The system provides API endpoints for querying books from the MongoDB and MinIO storage.

The primary purpose of the crawler service is to collect book information from a publicly available source, process it, and provide an easy-to-use interface for accessing this data. It serves a purpose of web scraping, data storage, message queuing, and the RESTful API.

Web Scraping:
The application utilizes the BeautifulSoup library to scrape book information from “www.authorama.com”. It collects all links containing book content with a maximum link depth of 2 and then crawls down all the contents from each link. While crawling down the contents, it extracts the chapter number from the URLs and retrieves details such as title, author, chapter, and content at the same time for each book. These book details are then saved as JSON files.

Data Storage:
The application uses MinIO, an object storage solution, to store the JSON files. It creates a client for MinIO storage and uploads each JSON file after it has been generated. In our current design, the crawled files were saved in a local temporary folder first then uploaded to MinIO, while the local folder could be cleared for more dynamic storage space management in the future. Metadata about the book, including its title, author, chapter, and MinIO storage location (the bucket name and the object), is stored in a MongoDB instance. This information is used later when querying books via the RESTful API.

Message Queuing:
For each book processed, a message is produced to a Kafka topic. This functionality is implemented using the confluent-kafka library. The Kafka Producer sends a message containing the book's ID to the topic, allowing SOLR services to consume these messages and perform further processing or analysis.

RESTful API:
The application provides a RESTful API using Flask and Flask-RESTful. Two API endpoints are available for querying books:
/query: This endpoint accepts query parameters such as 'id', 'title', 'author', 'chapter', 'bucket', and 'object'. It searches the MongoDB collection and returns book details stored in MinIO as JSON.
/search: This endpoint accepts a query parameter 'author' and returns a list of books authored by the specified author.
###3.3 Solr Service implementation
  First, how is the Solr server updated with all the book's data? Our Solr service acts as a Kafka Consumer. It subscribes to the ‘books’ topic and continuously polls for new messages. When the Solr service receives a message, it obtains the ID of the book from the message and makes a request to the web crawler to obtain the entire book information. We are using RESTful API to retrieve information from the crawler because the Kafka max message size is limited to 1MB though this size could be changed in the setting, but in our testing environment, it is stilled limited by the personal laptop memory. Due to this limitation, a RESTful API is used to send the book data to Solr server running at port 8983 to avoid overloading Kafka messages. 

  After initiating the crawler service and having the Solr server updated with book’s data, it is possible for us to query using Solr admin UI. By accessing the URL: localhost:8983 and use the core selector, we are able to query using the Solr admin UI as follows:
  

![Figure 2. SOLR cloud](https://github.com/cl6530/literature-search-big-data/blob/main/figures/SOLR_cloud.png)  
Figure 2. SOLR cloud

As seen in the screenshot above, when querying for content: “my readers have”, we have 2 books found. In the output, we can view every information regarding the book such as title, author, chapter, content, id, and version. Therefore, the Solr admin UI can be used for querying books that are stored in Solr server.

  Next, let’s discuss how we are implementing the web application with our Solr service. We use a simple RESTful API that handles the HTTP GET requests and allows us to extract information from the Solr server. The Solr service obtains parameters for the Solr query from the request arguments and constructs the Solr query URL. The Solr query URL is then sent to the Solr server, which returns a JSON response. We parse this response and return it as the HTTP response. The following screenshots show the results we are getting when we try to search for “my reader have” in the content field in a book. By using search everything, we are asking our Solr service to perform the query.

<p align="center">
  <img src="https://github.com/cl6530/literature-search-big-data/blob/main/figures/search_interface.png" alt="Figure 3. Searching results from UI" title="" width="200"/>
</p>  

![Figure 4. Searching results from UI](https://github.com/cl6530/literature-search-big-data/blob/main/figures/search_results_fromUI.png)  
Figure 3,4.  Searching results from UI

As we can see, there are two books that have “my readers have” in the content. Therefore, using a web application, our Solr service is able to return the query result as HTTP response using a RESTful API connecting between the web app and our Solr service. 

  Lastly, after carefully configuring the Solr service, there are several factors we need to consider. For example, what is the maximum storage capacity for our Solr service? In this case, the maximum storage capacity for data using Solr or Solr Cloud depends on various factors such as available disk space, indexing strategy and more. However, Solr itself does not impose a fixed storage limit.

  When considering indexing strategy, we can deploy techniques like merging index segments, implementing a data expiration policy, and excluding common and stop words. These policies can be added into our Solr service when we need to optimize storage efficiency in Solr.
 
  Ultimately, Solr does not have a hard limit on storage capacity. Nevertheless, it is a good practice to consistently monitor the storage usage and measure the search performance over time. This allows us to ensure efficient resource allocation and maintain an optimal search performance.
###3.4 Web app design
  The Web Application is our client facing service for file search. The backend is based on the Flask framework. On the UI, there are two types of searching, one is the exact search for the author name through MongoDB, and the other one is the fuzzy search for any type of book metadata through SOLR cloud. 

Exact Author Search
This search is for the exact author name search. When user input author name, the backend will first search our MongoDB through the our Web Crawler Service API to locate the object id (file path on MinIO). Then the backend calls the MinIO API to retrieve the file content and return them to the front end. 

Fuzzy Search 
The fuzzy search is enabled through SOLR service. After the user input the searching terms in the UI, the front end sends the payload to the backend, which calls SOLR service API. The front end payload is packaged into query conditions, which are used by SOLR for searching. The SOLR service will give each research result a score and rank the result in the descending order with the most relevant one on the top. Following is the result of searching “garden secret” in the content and it returned related books and chapters (clicking the hyperlink will show the full text of the chapter):
![Figure 5. Fuzzy search example](https://github.com/cl6530/literature-search-big-data/blob/main/figures/fuzzySearchresults.png)  
Figure 5. Fuzzy search example

 The full text of the content is not shown in the search result. Clicking the hyperlink will initiate a SOLR search based on the id of the associated content, and will return the full content text.
##4.	Conclusion
  In conclusion, we successfully implemented a full-stack big data searching framework that has good scalability, extensibility, maintainability, and high resilience. We successfully crawled, processed, and stored 3888 book chapters from www.authorama.com. We were able to search whole content, or related contents via keywords, authors, chapters, titles. The designed user-interactive application can also support highlighting in italic format, pagination for better display as well as home page return functions. 
##5.	Future works
  For the future works of this project, we can add a Cache component such as Redis at each service, for faster retrieval of information as shown in the figure below. The Redis at MinIO could cache the information of the latest books that were retrieved. The Redis at the MongoDB could cache the metadata such as path information, author, title, chapter number for faster file management. Redis at SOLR service could cache the most recent query results. We could add a cache component at the Web Application side as well for better performance.

  We can add a file metadata management microservice for better modularity, since the web crawler service is a bit heavy in our current system. In future we could put the new crawler service on more dedicated servers in this way. The communication from the Web Application to Web Crawler service in this case can be omitted, we leave the representation of this communication on the design just in case. We can provide more flexible and powerful crawling functions, for example being able to adapt to various website formatting, and use distributed web crawlers such as  Apache Nutch. This improvement could make the whole system more scalable. We can also support more searching functionalities to better demonstrate the powerful search capabilities of SOLR cloud.

![Figure 6. Future design](https://github.com/cl6530/literature-search-big-data/blob/main/figures/Future_design.png)
  
Figure 6. Future design of the search system architecture with cache and file management service







