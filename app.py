from flask import Flask, render_template, request, jsonify
import os, threading, time, random, requests
from datetime import datetime

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Global data
status_data = {
    "summary": {"success": 0, "failed": 0},
    "latest": {
        "comment_number": None,
        "comment": None,
        "full_comment": None,
        "token": None,
        "post_id": None,
        "profile_name": None,
        "timestamp": None,
        "status": None
    }
}
stop_flag = threading.Event()

def read_file_lines(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f.readlines() if line.strip()]

def get_profile_name(token):
    try:
        res = requests.get(f"https://graph.facebook.com/me?access_token={token}")
        return res.json().get("name", "Unknown")
    except:
        return "Unknown"

def validate_token(token):
    return get_profile_name(token) != "Unknown"

def comment_worker(token_path, comment_path, post_ids, first_name, last_name, delay):
    global status_data
    stop_flag.clear()
    status_data["summary"] = {"success": 0, "failed": 0}

    tokens = read_file_lines(token_path)
    comments = read_file_lines(comment_path)
    post_ids = [x.strip() for x in post_ids.split(",") if x.strip()]
    valid_tokens = [t for t in tokens if validate_token(t)]

    if not valid_tokens or not comments or not post_ids:
        return

    comment_num = 0
    while not stop_flag.is_set():
        token = valid_tokens[comment_num % len(valid_tokens)]
        comment = comments[comment_num % len(comments)]
        post_id = post_ids[comment_num % len(post_ids)]
        profile_name = get_profile_name(token)
        full_comment = " ".join(filter(None, [first_name, comment, last_name]))

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        token_index = comment_num % len(valid_tokens)

        try:
            res = requests.post(f"https://graph.facebook.com/{post_id}/comments", data={
                "message": full_comment,
                "access_token": token
            })
            result = res.json()
            if "id" in result:
                status_data["summary"]["success"] += 1
                status = "Success"
            else:
                status_data["summary"]["failed"] += 1
                status = "Failed"
        except:
            status_data["summary"]["failed"] += 1
            status = "Failed"

        status_data["latest"] = {
            "comment_number": comment_num + 1,
            "comment": comment,
            "full_comment": full_comment,
            "token": f"Token #{token_index+1}",
            "post_id": post_id,
            "profile_name": profile_name,
            "timestamp": timestamp,
            "status": status
        }

        comment_num += 1
        time.sleep(random.randint(delay, delay + 5))

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        token_file = request.files['token_file']
        comment_file = request.files['comment_file']
        post_ids = request.form.get('post_ids')
        first_name = request.form.get('first_name', '')
        last_name = request.form.get('last_name', '')
        delay = max(60, int(request.form.get('delay', 60)))

        token_path = os.path.join(UPLOAD_FOLDER, 'tokens.txt')
        comment_path = os.path.join(UPLOAD_FOLDER, 'comments.txt')
        token_file.save(token_path)
        comment_file.save(comment_path)

        threading.Thread(
            target=comment_worker,
            args=(token_path, comment_path, post_ids, first_name, last_name, delay),
            daemon=True
        ).start()

        return jsonify({"message": "Commenting started!"})
    return render_template('index.html')

@app.route('/stop', methods=['POST'])
def stop():
    stop_flag.set()
    return jsonify({"message": "Stopped commenting."})

@app.route('/status')
def status():
    return jsonify(status_data)

if __name__ == '__main__':
    import socket
    s = socket.socket()
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()
    print(f"Running on http://127.0.0.1:{port}")
    app.run(debug=True, port=port)