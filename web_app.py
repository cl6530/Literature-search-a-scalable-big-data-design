from flask import Flask, render_template, request, session, url_for, redirect, flash
import requests
import json

from werkzeug.wrappers import response

app = Flask(__name__)

# Home Page
# MongoDB:
#  search by author
# Solr: 
#  search by author
#  search by content
#  search by title
#  search by chapter

@app.route('/')
def landing():
    return render_template('home.html')

@app.route('/mongo_search', methods=['POST'])
def mongo_search():
    author = request.form['author']
    if author is None or author == "":
        return render_template('search.html', error="Author name is empty!")
    else:
        web_svc_parms = {
            "author": author
        }
        web_svc_url = 'http://localhost:8888/query'
        results = requests.get(web_svc_url, params=web_svc_parms).json()
        return render_template('search.html', results=results)

@app.route('/solr_read', methods=['GET'])
def solr_read():
    id = request.args.get('id')
    if id is None or id == "":
        return render_template('read.html', error="Invali id!")
    else:
        solr_svc_parms = {
            "q": f"id:{id}"
        }

        solr_svc_url = 'http://localhost:8887/query'
        response = requests.get(solr_svc_url, params=solr_svc_parms).json()
        return render_template('read.html', response=response["response"]["docs"][0])

@app.route('/solr_search', methods=['GET', 'POST'])
def solr_search():
    if request.method == 'POST':
        author = request.form['author']
        content = request.form['content']
        title = request.form['title']
        chapter = request.form['chapter']
        start = -1
        rows = 20
    else:
        author = request.args.get('author')
        content = request.args.get('content')
        title = request.args.get('title')
        chapter = request.args.get('chapter')
        start = request.args.get('start')
        rows = request.args.get('rows')
    if start is None or rows is None:
        return render_template('search.html', error="Specify page number!")
    else:
        start = int(start)
        rows = int(rows)
        if start >= 0:
            start += rows
        else:
            start = 0

        q = "*:*"
        if author is not None and author != "":
            q = f'author:{author}~10'
        
        q_op = "OR"
        fq = []

        if content is not None and content != "":
            if q != "*:*":
                q_op = "AND"
                fq.append(f'content:"{content}"~50')
            else:
                q = f'content:"{content}"~50'

        if title is not None and title != "":
            if q != "*:*":
                q_op = "AND"
                fq.append(f'title:"{title}"~15')
            else:
                q = f'title:"{title}"~15'

        if chapter is not None and chapter != "":
            if q != "*:*":
                q_op = "AND"
                fq.append(f'chapter:"{chapter}"')
            else:
                q = f'chapter:"{chapter}"'

        solr_svc_parms = {}
        solr_svc_parms["q"] = q
        solr_svc_parms["q.op"] = q_op
        solr_svc_parms["hl"] = "true"
        solr_svc_parms["indent"] = "true"
        solr_svc_parms["hl.fl"] = "*"
        solr_svc_parms["sort"] = "score desc"
        solr_svc_parms["start"] = f'{start}'
        solr_svc_parms["rows"] = f'{rows}'
        if len(fq) == 1:
            solr_svc_parms["fq"] = fq[0]
        elif len(fq) > 1:
            solr_svc_parms["fq"] = fq

        solr_svc_url = 'http://localhost:8887/query'
        response = requests.get(solr_svc_url, params=solr_svc_parms).json()
        results = []
        id_map = {}

        print(f'resp={response["response"]}')

        for doc in response["response"]["docs"]:
            tmp_title = ""
            tmp_author = ""
            tmp_chap = ""
            if "title" in doc:
                tmp_title = doc["title"]
            if "author" in doc:
                tmp_author = doc["author"]
            if "chapter" in doc:
                tmp_chap = doc["chapter"]
            results.append({
                "title": tmp_title,
                "author": tmp_author,
                "chapter": tmp_chap,
                "id": doc["id"]
            })
            id_map[doc["id"]] = len(results) - 1
        
        for id in response["highlighting"]:
            idx = id_map[id]
            if "title" in response["highlighting"][id]:
                results[idx]["title"] = response["highlighting"][id]["title"]
            if "author" in response["highlighting"][id]:
                results[idx]["author"] = response["highlighting"][id]["author"]
            if "content" in response["highlighting"][id]:
                results[idx]["content"] = response["highlighting"][id]["content"]

        return render_template('search.html', results=results, response=response, author=author, content=content, 
            title=title, chapter=chapter, start=start, rows=rows, solr=True)

if __name__ == "__main__":
    app.run(debug=False, port=8886)