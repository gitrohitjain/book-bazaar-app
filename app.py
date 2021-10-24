from flask import Flask, request, render_template, redirect, request, session, url_for
from flask_bootstrap import Bootstrap
from flask_wtf import FlaskForm
# from wtforms import StringField, SubmitField, FileField, RadioField
# from wtforms.validators import DataRequired
import os
import random
import string
import sqlite3
from datetime import datetime
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'C2HWGVoMGfNTBsrYQg8EcMrdTimkZfAb'
app.config['UPLOAD_FOLDER'] = 'static/temp/'
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
Bootstrap(app)


@app.route('/')
def root():
    createTableBooks()
    createTableUsers()
    return redirect('/login') 


@app.route('/login', methods=['GET','POST'])
def login():
    ERROR = ""
    MATCH = False
    if request.method == 'POST':
        username = request.form['username']
        con,cur = create_userdb_connection()
        cur.execute(f"SELECT * FROM users WHERE user_username='{username}'")
        user = cur.fetchall()

        if len(user) == 0:
            ERROR = f'No such user {username} exists'
        else:
            cur.execute(f"SELECT user_pass FROM users WHERE user_username='{username}'")
            db_pass = cur.fetchall()[0][0]
            password = request.form['password']
            if db_pass == password:
                MATCH = True
                session['USER'] = username
            else:
                ERROR = 'Password is Wrong'

        con.commit()
        con.close()
    
    if not MATCH:
        return render_template('login.html', error = ERROR)
    else:
        return redirect('/index')


@app.route('/register', methods=['GET','POST'])
def register():
    ERROR = False
    SUCCESS = False
    username=""
    if request.method == 'POST':
        name = request.form['name']
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        user_id = int(''.join(random.choices(string.digits, k=16)))

        user_ins = f"""INSERT INTO users VALUES (
        '{user_id}', '{name}', '{username}',
        '{email}', '{password}','{str(datetime.now())}', '0'        
        )"""
        
        print(user_ins)

        con, cur = create_userdb_connection()
        try:
            cur.execute(user_ins)
            SUCCESS = True
        except Exception as e:
            print('ERROR :', e)
            ERROR = True
        con.commit()
        con.close()


    # if ERROR:
        # return render_template('register.html', success=SUCCESS, error=ERROR)
    # elif SUCCESS:
        # return render_template('register.html', success=SUCCESS, error=ERROR)
    # else:
    return render_template('register.html', success=SUCCESS, error=ERROR, username=username)


@app.route('/index')
def index():
    return render_template('index.html', users_name=getUsersFullName(session['USER']))


@app.route('/buy_list')
def buy_list():
    all_books = list_to_listdict(query_all_records_others('books'))
    return render_template('buy_list.html', all_books=all_books)


@app.route('/buy_one/<bid>')
def buy_one(bid):
    one_book = list_to_listdict(query_one_record('books', 'book_id', bid))[0]
    return render_template('buy_one.html', one_book=one_book)


@app.route('/buy_one/<incoming>/success')
def buy_successful(incoming):
    credit_one_that_is_author = False
    arr = incoming.split('-')
    bid, bp = arr[0], float(arr[1]) #use bp, bp is gas fee from listing

    one_book = list_to_listdict(query_one_record('books', 'book_id', bid))[0]

    init_owner = get_last_owner(bid)
    before_owner= one_book['bco']
    
    update_owner = f'''UPDATE books
    SET current_owner='{session['USER']}',last_owner='{before_owner}'
    WHERE book_id={bid};
    '''
    con, cur = create_booksdb_connection()
    cur.execute(update_owner)
    con.commit()
    con.close()
    
    book_price = float(get_book_price(bid))
    gf = bp-book_price

    curr_owner_curr_wallet_balance = float(get_curr_balance(session['USER']))
    curr_owner_updated_balance = curr_owner_curr_wallet_balance - (book_price+gf)
    cur_owner_update_user_wallet = f'''UPDATE users
    SET cur_balance='{curr_owner_updated_balance}'
    WHERE user_username='{session['USER']}'
    '''
    con,cur = create_userdb_connection()
    cur.execute(cur_owner_update_user_wallet)
    con.commit()
    con.close()

    author_amt = 0
    new_person_amt = 0
    LAST_OWNER = get_last_owner(bid)
    AUTHOR = get_book_author(bid)

    loyalty = 0.1 * book_price
    first_mint_fee = 0
    seller_gets = 0.9 * book_price

    if init_owner == "None":
        loyalty = 0
        first_mint_fee = 0.05 * book_price
        seller_gets = book_price

    updated_author_balance = float(get_curr_balance(AUTHOR)) + loyalty - first_mint_fee
    deduct_mint_fee_from_author = f'''UPDATE users
    SET cur_balance='{updated_author_balance}'
    WHERE user_username='{AUTHOR}'
    '''
    con,cur = create_userdb_connection()
    cur.execute(deduct_mint_fee_from_author)
    con.commit()
    con.close()

    
    last_owner_curr_wallet_balance = float(get_curr_balance(LAST_OWNER))
    last_owner_updated_balance = last_owner_curr_wallet_balance + seller_gets
    
    last_owner_update_user_wallet = f'''UPDATE users
    SET cur_balance='{last_owner_updated_balance}'
    WHERE user_username='{get_last_owner(bid)}'
    '''
    con,cur = create_userdb_connection()
    cur.execute(last_owner_update_user_wallet)
    con.commit()
    con.close()
    
    update_admin_balance_by(gf+first_mint_fee)

    unsetListedBySelf(bid)

    ADDED=True
    
    if ADDED:
        return render_template("buy_successful.html", given=True, one_book=one_book, balance=get_curr_balance(session['USER']))
    else:
        return render_template("buy_successful.html", given=False,one_book=one_book)



@app.route('/sell_from_library')
def sell_from_library():
    all_books = list_to_listdict(query_all_records_self_that_can_be_sold('books'))
    return render_template('sell_from_library.html', all_books=all_books)


@app.route('/sell_one/<bid>')
def sell_one(bid):
    one_book = list_to_listdict(query_one_record('books', 'book_id', bid))[0]
    return render_template('sell_one.html', one_book=one_book)


@app.route('/sell_one/<incoming>/success')
def sell_successful(incoming):
    bid, speed, set_price = incoming.split('-')

    if speed == 'fast':
        deduct = 0.02 * float(set_price)
    else:
        deduct = 0.01 * float(set_price)

    update_price = f'''UPDATE books
    SET book_price='{set_price}'
    WHERE book_id={bid};
    '''
    
    con, cur = create_booksdb_connection()
    cur.execute(update_price)
    con.commit()
    con.close()

    update_admin_balance_by(deduct)

    curr_owner_updated_balance = float(get_curr_balance(session['USER'])) - deduct
    cur_owner_update_user_wallet = f'''UPDATE users
    SET cur_balance='{curr_owner_updated_balance}'
    WHERE user_username='{session['USER']}'
    '''
    con,cur = create_userdb_connection()
    cur.execute(cur_owner_update_user_wallet)
    con.commit()
    con.close()

    setListedBySelf(bid)

    return render_template('sell_successful.html')


@app.route('/sell_main')
def sell_main():
    return render_template('sell_main.html')


@app.route('/list_now_pay')
def list_now_pay():
    return "Welcome"


@app.route('/list_new', methods=['GET', 'POST'])
def list_new():
    POST = False
    if request.method == 'POST':
        POST = True
        name = request.form['name']
        desc = request.form['desc']
        price = request.form['price']
        # speed = request.form['speed']
        image = request.files['img']
        image.save(app.config['UPLOAD_FOLDER'] + image.filename)

        item= {
            "b_id" : int(''.join(random.choices(string.digits, k=16))),
            "book_name" : name,
            "book_price" : price,
            "book_desc" : desc,
            "current_owner": session['USER'],
            "last_owner": None,
            "author" : session['USER'],
            "image_path" : image.filename,
            "upload_date" : str(datetime.now()),
        }

        ins = f"""INSERT INTO books VALUES (
        {item['b_id']}, "{item['book_name']}", "{item['book_price']}",
        "{item['book_desc']}", "{item['current_owner']}","{item['last_owner']}","{item['author']}", 
        "{item['image_path']}", "{item['upload_date']}", 'None' , 'None' , 'None', 'None', 'None'    
        )"""
        
        con, cur = create_booksdb_connection()
        cur.execute(ins)
        con.commit()
        con.close()

        setListedBySelf(item['b_id'])
        # goes_to_admin = round((2.5/100) * float(price) if speed=="fast" else (1.5/100) * float(price),4)
        # update_admin_balance_by(goes_to_admin)

        # curr_owner_updated_balance = float(get_curr_balance(session['USER'])) - goes_to_admin
        # cur_owner_update_user_wallet = f'''UPDATE users
        # SET cur_balance='{curr_owner_updated_balance}'
        # WHERE user_username='{session['USER']}'
        # '''
        # con,cur = create_userdb_connection()
        # cur.execute(cur_owner_update_user_wallet)
        # con.commit()
        # con.close()
       
    
    return render_template('list_new.html', display= POST)


@app.route('/library')
def library():
    all_books = list_to_listdict(query_all_my_bought_and_borrowed())
    return render_template('library.html', all_books=all_books, users_name=getUsersFullName(session['USER']))
    

@app.route('/all_listed_books')
def fetch_listed():
    all_books = list_to_listdict(fetch_all_listed_books())
    return render_template('all_listed_books.html', all_books=all_books)


@app.route('/mywallet')
def mywallet():
    return render_template('wallet.html', user_balance=get_curr_balance(session['USER']), users_name=getUsersFullName(session['USER']))



@app.route('/recharge')
def recharge():
    return render_template("recharge.html", all_books=['metamask','coinbase','bitski','walletconnect'])


@app.route('/add_balance', methods=['GET', 'POST'])
def add_balance():
    ADDED = False
    if request.method == 'POST':
        money = request.form['money']
        incoming = float(money)
        already = float(get_curr_balance(session['USER']))
        updated = incoming + already
        
        inscmd = f'''UPDATE users
        SET cur_balance='{updated}'
        WHERE user_username='{session['USER']}'
        '''
        con,cur = create_userdb_connection()
        cur.execute(inscmd)
        ADDED=True
        con.commit()
        con.close()
   
    if ADDED:
        return render_template("add_balance.html", given=True, money=money)
    else:
        return render_template("add_balance.html", given=False)


@app.route('/admin_balance')
def admin_balance():
    return render_template('admin_wallet.html',balance= f"{round(float(get_curr_balance('admin')), 4)}")


@app.route('/loan_main')
def loan_main():
    all_books = list_to_listdict(query_all_records_self_that_can_be_sold('books'))
    return render_template('loan_main.html', all_books=all_books)


@app.route('/loan_one/<bid>')
def loan_one(bid):
    one_book = list_to_listdict(query_one_record('books', 'book_id', bid))[0]
    return render_template('loan_one.html', one_book=one_book)


@app.route('/loan_one/<incoming>/success')
def loan_one_success(incoming):
    bid, loan_price, loan_period = incoming.split('-')
    setLoanListed(bid)
    set_loan_period(bid, loan_period)
    set_loan_price(bid, loan_price)
    return render_template('loan_successful.html')


@app.route('/borrow_main')
def borrow_main():
    all_books = list_to_listdict(query_all_that_can_be_borrowed())
    return render_template('borrow_main.html', all_books=all_books)


@app.route('/borrow_one/<incoming>/success')
def borrow_one_success(incoming):
    
    bid, borrow_price, borrow_period = incoming.split('-')
    unsetLoanListed(bid)
    setBorrowed(bid)
    borrow_price = float(borrow_price)
    gf = (2.5/100) * borrow_price

    one_book = list_to_listdict(query_one_record('books', 'book_id', bid))[0]
    init_owner = get_last_owner(bid)
    before_owner= one_book['bco']
    update_owner = f'''UPDATE books
    SET current_owner='{session['USER']}',last_owner='{before_owner}'
    WHERE book_id={bid};
    '''
    con, cur = create_booksdb_connection()
    cur.execute(update_owner)
    con.commit()
    con.close()

    curr_owner_curr_wallet_balance = float(get_curr_balance(session['USER']))
    curr_owner_updated_balance = curr_owner_curr_wallet_balance - (borrow_price+gf)
    cur_owner_update_user_wallet = f'''UPDATE users
    SET cur_balance='{curr_owner_updated_balance}'
    WHERE user_username='{session['USER']}'
    '''
    con,cur = create_userdb_connection()
    cur.execute(cur_owner_update_user_wallet)
    con.commit()
    con.close()

    AUTHOR = get_book_author(bid)
    updated_author_balance = float(get_curr_balance(AUTHOR)) + (0.05*borrow_price)
    deduct_mint_fee_from_author = f'''UPDATE users
    SET cur_balance='{updated_author_balance}'
    WHERE user_username='{AUTHOR}'
    '''
    con,cur = create_userdb_connection()
    cur.execute(deduct_mint_fee_from_author)
    con.commit()
    con.close()

    LAST_OWNER = get_last_owner(bid)
    last_owner_curr_wallet_balance = float(get_curr_balance(LAST_OWNER))
    last_owner_updated_balance = last_owner_curr_wallet_balance + borrow_price - gf
    
    last_owner_update_user_wallet = f'''UPDATE users
    SET cur_balance='{last_owner_updated_balance}'
    WHERE user_username='{LAST_OWNER}'
    '''
    con,cur = create_userdb_connection()
    cur.execute(last_owner_update_user_wallet)
    con.commit()
    con.close()
    
    update_admin_balance_by(2*gf)


    return render_template('borrow_successful.html')


@app.route('/all_borrowed')
def all_borrowed():
    all_books = list_to_listdict(queryAllBorrowed())
    return render_template('all_borrowed.html', all_books=all_books)
    
    
@app.route('/wishlist')
def wishlist():
    all_books = list_to_listdict(query_all_records_others('books'))
    return render_template('wishlist.html', all_books=all_books)





def queryAllBorrowed():
    con, cur = create_booksdb_connection()
    cur.execute(f"""SELECT * FROM books
    WHERE current_owner='{session['USER']}' 
    AND is_borrowed='True'
    """)
    results= cur.fetchall()
    con.commit()
    con.close()
    return results


def setBorrowed(bid):
    cmd = f'''UPDATE books
    SET is_borrowed='True'
    WHERE book_id={bid};
    '''
    con, cur = create_booksdb_connection()
    cur.execute(cmd)
    con.commit()
    con.close()


def unsetBorrowed(bid):
    cmd = f'''UPDATE books
    SET is_borrowed='None'
    WHERE book_id={bid};
    '''
    con, cur = create_booksdb_connection()
    cur.execute(cmd)
    con.commit()
    con.close()


def set_loan_price(bid, loan_price):
    cmd = f'''UPDATE books
    SET loan_price='{loan_price}'
    WHERE book_id={bid};
    '''
    con, cur = create_booksdb_connection()
    cur.execute(cmd)
    con.commit()
    con.close()


def set_loan_period(bid, period):
    cmd = f'''UPDATE books
    SET loan_period='{period}'
    WHERE book_id={bid};
    '''
    con, cur = create_booksdb_connection()
    cur.execute(cmd)
    con.commit()
    con.close()

#query all loan listed books. TBC, create new route side menu
def list_loaned_out():
    con, cur = create_booksdb_connection()
    cur.execute(f"""SELECT * FROM books 
    WHERE current_owner='{session['USER']}' 
    AND loan_listed='True'
    """)
    results= cur.fetchall()
    con.commit()
    con.close()
    return results


def setLoanListed(bid):
    cmd = f'''UPDATE books
    SET loan_listed='True'
    WHERE book_id={bid};
    '''
    con, cur = create_booksdb_connection()
    cur.execute(cmd)
    con.commit()
    con.close()

def unsetLoanListed(bid):
    cmd = f'''UPDATE books
    SET loan_listed='None'
    WHERE book_id={bid};
    '''
    con, cur = create_booksdb_connection()
    cur.execute(cmd)
    con.commit()
    con.close()


def setListedBySelf(bid):
    cmd = f'''UPDATE books
    SET listed='True'
    WHERE book_id={bid};
    '''
    con, cur = create_booksdb_connection()
    cur.execute(cmd)
    con.commit()
    con.close()


def unsetListedBySelf(bid):
    cmd = f'''UPDATE books
    SET listed='None'
    WHERE book_id={bid};
    '''
    con, cur = create_booksdb_connection()
    cur.execute(cmd)
    con.commit()
    con.close()


def get_book_author(bid):
    con, cur = create_booksdb_connection()
    cur.execute(f"SELECT author_name FROM books WHERE book_id='{bid}'")
    answer = cur.fetchall()[0][0]
    con.commit()
    con.close()
    return answer


def update_admin_balance_by(amount):
    old_balance= float(get_curr_balance('admin'))
    incoming = float(amount)
    admin_updated_balance = old_balance + incoming
    updcmd = f'''UPDATE users
    SET cur_balance='{admin_updated_balance}'
    WHERE user_username='admin'
    '''
    con,cur = create_userdb_connection()
    cur.execute(updcmd)
    con.commit()
    con.close()


def get_last_owner(bid):
    con, cur = create_booksdb_connection()
    cur.execute(f"SELECT last_owner FROM books WHERE book_id='{bid}'")
    answer = cur.fetchall()[0][0]
    con.commit()
    con.close()
    return answer


def get_book_price(bid):
    con, cur = create_booksdb_connection()
    cur.execute(f"SELECT book_price FROM books WHERE book_id='{bid}'")
    answer = cur.fetchall()[0][0]
    con.commit()
    con.close()
    return answer


def get_curr_balance(username):
    con,cur = create_userdb_connection()
    cur.execute(f"SELECT cur_balance FROM users WHERE user_username='{username}'")
    answer = cur.fetchall()[0][0]
    con.commit()
    con.close()
    if answer is None:
        return 0
    return answer


def getUsersFullName(username):
    con,cur = create_userdb_connection()
    cur.execute(f"SELECT user_name FROM users WHERE user_username='{username}'")
    answer = cur.fetchall()[0][0]
    con.commit()
    con.close()
    return answer


def createTableBooks():
    con, cur = create_booksdb_connection()
    cmd_create_books  =  f'''CREATE TABLE IF NOT EXISTS books (
    book_id BIGINT PRIMARY KEY, 
    book_name TEXT, 
    book_price TEXT,
    book_desc TEXT,
    current_owner TEXT,
    last_owner TEXT,
    author_name TEXT,
    image_path TEXT,
    upload_date TEXT,
    listed TEXT,
    loan_listed TEXT DEFAULT "None",
    loan_period TEXT,   
    loan_price TEXT,
    is_borrowed TEXT DEFAULT "None"
    )'''
    cur.execute(cmd_create_books)
    con.commit()
    con.close()
    print('BOOKS TABLE CREATED!!')


def createTableUsers():
    con, cur = create_userdb_connection()
    cmd_create_users =  f'''CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY, 
    user_name TEXT,
    user_username TEXT NOT NULL UNIQUE,  
    user_email TEXT,
    user_pass TEXT,
    user_created_date TEXT,
    cur_balance TEXT   
    )'''
    cur.execute(cmd_create_users)

    try:
        print(getUsersFullName('admin'))
    except:
        create_admin_cmd = """INSERT INTO users VALUES (
        '001', 'admin', 'admin',
        'admin@admin.admin', 'admin','admin','0'        
        )"""
        cur.execute(create_admin_cmd)

    con.commit()
    con.close()
    print('USERS TABLE CREATED!!')


def printDB(tableName):
    if tableName == 'books':
        con, cur = create_booksdb_connection()
    elif tableName == 'users':
        con, cur = create_userdb_connection()
    cur.execute(f"SELECT * FROM {tableName}")
    results = cur.fetchall()
    con.commit()
    con.close()
    print(results)


def list_to_listdict(lst):
    keys = ['bid', 'bname', 'bprice', 'bdesc', 'bco', 'blo','bauthor','bip','bud','blisted','bloanlisted','bloanperiod','bloanprice','is_borrowed']
    main = []
    for b in lst:
        bd = {}
        for i, v in enumerate(b):
            bd[keys[i]] = v
        main.append(bd)
    return main


def query_all_records_others(tableName):
    if tableName == 'books':
        con, cur = create_booksdb_connection()
    elif tableName == 'users':
        con, cur = create_userdb_connection()

    cur.execute(f"""SELECT * FROM {tableName} 
    WHERE NOT current_owner='{session['USER']}'
    AND listed='True'
    """)
    results= cur.fetchall()
    con.commit()
    con.close()
    return results


def query_all_that_can_be_borrowed():
    con, cur = create_booksdb_connection()
    cur.execute(f"""SELECT * FROM books
    WHERE NOT current_owner='{session['USER']}' 
    AND loan_listed='True'
    AND is_borrowed='None'
    """)
    results= cur.fetchall()
    con.commit()
    con.close()
    return results


def query_all_my_bought_and_borrowed():
    con, cur = create_booksdb_connection()
    cur.execute(f"""SELECT * FROM books 
    WHERE current_owner='{session['USER']}' 
    AND NOT last_owner='None'
    AND listed='None'
    AND loan_listed='None'
    AND is_borrowed='True'
    """)
    results= cur.fetchall()
    con.commit()
    con.close()
    return results


def query_all_records_self_that_can_be_sold(tableName):
    if tableName == 'books':
        con, cur = create_booksdb_connection()
    elif tableName == 'users':
        con, cur = create_userdb_connection()

    cur.execute(f"""SELECT * FROM {tableName} 
    WHERE current_owner='{session['USER']}' 
    AND NOT last_owner='None'
    AND listed='None'
    AND loan_listed='None'
    AND is_borrowed='None'
    """)
    results= cur.fetchall()
    con.commit()
    con.close()
    return results


def fetch_all_listed_books():
    con, cur = create_booksdb_connection()
    cur.execute(f"""SELECT * FROM books 
    WHERE current_owner='{session['USER']}' 
    AND (listed='True' OR loan_listed='True')
    """)
    results= cur.fetchall()
    con.commit()
    con.close()
    return results
    # AND last_owner='None'


def query_one_record(tableName, key, value):
    if tableName == 'books':
        con, cur = create_booksdb_connection()
    elif tableName == 'users':
        con, cur = create_userdb_connection()

    cur.execute(f"SELECT * FROM {tableName} WHERE {key}={value};")
    results = cur.fetchall()
    con.commit()
    con.close()
    return results


def create_booksdb_connection():
    books_con = sqlite3.connect('file:booksdb', check_same_thread=False)
    cur = books_con.cursor()
    return books_con, cur


def create_userdb_connection():
    users_con = sqlite3.connect('file:usersdb', check_same_thread=False)
    cur = users_con.cursor()
    return users_con, cur


if __name__ == "__main__":
    createTableBooks()
    createTableUsers()
    app.run(debug=True)

   