import os
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
import PyPDF2
import ollama

import mysql.connector
app = Flask(__name__)
app.secret_key = 'your_secret_key'
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'XXXXX'
}

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')


def extract_text_from_pdf(pdf_file_path):
    text = ""
    with open(pdf_file_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        num_pages = len(reader.pages)
        for page_number in range(num_pages):
            page = reader.pages[page_number]
            text += page.extract_text()
    return text

@app.route('/')
def index():
    return render_template('hero.html')

@app.route('/newacc', methods=['POST'])
def newacc():
    first_name = request.form['firstName']
    last_name = request.form['lastName']
    username = request.form['username']
    email = request.form['email']
    age = int(request.form['age'])
    gender = request.form['gender']
    password = request.form['password']

    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()

    # Insert user into the user table
    cursor.execute("INSERT INTO user (first_name, last_name, username, email, age, gender, password) VALUES (%s, %s, %s, %s, %s, %s, %s)", 
                   (first_name, last_name, username, email, age, gender, password))
    
    # Insert user into the user_upload_count table with upload_count set to 0
    cursor.execute("INSERT INTO user_upload_count (username, upload_count) VALUES (%s, 0)", (username,))
    
    conn.commit()
    conn.close()

    return render_template('login.html')


@app.route('/acccreate')
def acccreate():
    return render_template('accountcreate.html')


@app.route('/submit_complaint', methods=['POST'])
def submit_complaint():
    # Check if the request contains form data
    if request.method == 'POST':
        # Extract data from the form submission
        email = request.form.get('email')
        name = request.form.get('name')
        message = request.form.get('message')
        
        # Connect to the MySQL database
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        try:
            # Insert the complaint into the database
            cursor.execute("INSERT INTO complaints (email, name, message) VALUES (%s, %s, %s)", (email, name, message))
            conn.commit()
            
            # Close database connection
            cursor.close()
            conn.close()
            
            # Return a success response
            return jsonify({'message': 'Complaint submitted successfully!'})
        except Exception as e:
            # Return an error response if something goes wrong
            return jsonify({'error': str(e)})
    else:
        # Return an error response if the request method is not POST
        return jsonify({'error': 'Invalid request method'})


@app.route('/submit', methods=['POST'])
def submit():
    username = request.form['username']
    password = request.form['password']

    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM user WHERE username = %s AND password = %s", (username, password))
    user = cursor.fetchone()

    conn.close()

    if user:
        # Store user in session
        session['user'] = user
        return redirect(url_for('index_page'))
    else:
        return redirect(url_for('login', message='Invalid username or password'))



@app.route('/subscribe', methods=['POST'])
def subscribe():
    email = request.form['email']
    full_name = request.form['name']
    card_number = request.form['cardNumber']
    expiry_date = request.form['expiryDate']
    cvv = request.form['cvv']

    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()

    try:
        # Insert subscription data into the user_subscriptions table
        cursor.execute("INSERT INTO user_subscriptions (email, full_name, card_number, expiry_date, cvv) VALUES (%s, %s, %s, %s, %s)", 
                       (email, full_name, card_number, expiry_date, cvv))
        conn.commit()
        
        cursor.close()
        conn.close()

        return redirect(url_for('index'))  # Redirect to homepage after successful subscription
    except Exception as e:
        return render_template('error.html', message='Failed to subscribe. Please try again later.')  # Render an error template if subscription fails


@app.route('/login')
def login():
    # Check if user is already logged in
    # if 'user' in session:
    #     return redirect(url_for('index_page'))
    return render_template('login.html')

@app.route('/logout',methods=['POST','GET','PUT'])
def logout():
    # Clear session data
    
    session.pop('user', None)
    return render_template('hero.html')

# Add a new route to fetch the upload count
@app.route('/get_upload_count',methods=['GET'])
def get_upload_count():
    if 'user' in session:
        user = session['user']
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("SELECT upload_count FROM user_upload_count WHERE username = %s", (user[2],))
        # upload_count = cursor.fetchone()[0]
        upload_count = cursor.fetchone()
        if upload_count is not None:
            upload_count = upload_count[0]
        else:
            upload_count = 0
        conn.close()
        return jsonify({'upload_count': upload_count})
    else:
        return jsonify({'upload_count': 0})  # Return 0 if user is not logged in


@app.route('/index_page',methods=['POST','GET','PUT'])
def index_page():
    if 'user' in session:
        user = session['user']
        username = user[2]  # Assuming the username is stored in the second column
        
        # Retrieve upload count for the user
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("SELECT upload_count FROM user_upload_count WHERE username = %s", (user[2],))  # Assuming user_id is stored in the first column
        # upload_count = cursor.fetchone()[0]
        upload_count = cursor.fetchone()
        if upload_count is not None:
            upload_count = upload_count[0]
        else:
            upload_count = 0  

        conn.close()
        
        return render_template('index.html', username=username, upload_count=upload_count)
    else:
        return redirect(url_for('login'))


@app.route('/doc_page')
def doc_page():
    return render_template('doc.html')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/upload', methods=['POST'])
def upload():
    global text
    if 'pdfFile' not in request.files:
        return jsonify({'error': 'No file part'})

    file = request.files['pdfFile']
    if file.filename == '':
        return jsonify({'error': 'No selected file'})

    if 'user' not in session:
        return jsonify({'error': 'User not logged in'})
    
    user = session['user']
    
    # Retrieve the current upload count for the user
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("SELECT upload_count FROM user_upload_count WHERE username = %s", (user[2],))
    # upload_count = cursor.fetchone()[0]
    upload_count = cursor.fetchone()
    if upload_count is not None:
        upload_count = upload_count[0]
    else:
        upload_count = 0 

    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("SELECT subscription_status FROM user_subscriptions WHERE email = %s AND subscription_status = 'active'", (user[3],))
    subscription_status = cursor.fetchone()
    # Check if user has exceeded the upload limit
    if upload_count >= 10 and not subscription_status:
        conn.close()
        return jsonify({'error': 'Upload limit exceeded. Please subscribe to continue uploading.'})
    
    # Increment the upload count
    if subscription_status :
        # Handle file upload logic here
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(file_path)
        
        # Extract text from PDF           
        text = extract_text_from_pdf(file_path)
        
        # Return JSON response with upload count
        return jsonify({'upload_count': upload_count })
    else:
        cursor.execute("UPDATE user_upload_count SET upload_count = upload_count + 1 WHERE username = %s", (user[2],))
        conn.commit()
        conn.close()

        # Handle file upload logic here
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(file_path)
        
        # Extract text from PDF           
        text = extract_text_from_pdf(file_path)
        
        # Return JSON response with upload count
        return jsonify({'upload_count': upload_count + 1})
        # return upload_count

    
          
@app.route('/ask', methods=['POST'])
def ask():
    global text
    data = request.json
    prompt = data.get('question', '')
    extra="if answer is short of if suit pointwise answer than give answer in pointwise format"
    response = ollama.chat(model='llama2', messages=[{'role': 'user', 'content':text+prompt}])
    ans = response['message']['content']
                 
    return ans,200
    # return prompt, 200
    # return que, 200

@app.route('/contact_html', methods=['GET'])
def contact_html():
    return render_template('contactus.html')

@app.route('/form_sub', methods=['GET'])
def form_sub():
    return render_template('subscription.html')

# Define route to handle chat interface
@app.route('/chats', methods=['GET'])
def chats():
    return render_template('chat.html')

# Define route to process user input and generate bot response
@app.route('/process_data', methods=['POST'])
def process_data():
    data = request.json
    user_input = data.get('user_input')

    output=user_input+"respose"
    # Call the chatbot model and get response
    response = ollama.chat(model='llama2', messages=[{'role': 'user', 'content': user_input}])
    bot_reply = response['message']['content']

    return bot_reply,200

if __name__ == '__main__':
    app.run(debug=True, port=5500)
