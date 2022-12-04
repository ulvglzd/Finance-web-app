import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user_id = session["user_id"]

    """storing the purchased items into variable "product" and create new variable
    user_balance to store the cash user has"""
    products = db.execute("SELECT symbol, SUM(shares) AS sum_shares, price FROM history WHERE user_id = ? GROUP BY symbol", user_id)
    user_balance = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]

    total = user_balance
    #looping through each type of products and summing the current price of products and add them to user's cash
    for product in products:
        total += product["price"] * product["sum_shares"]

    return render_template("index.html", products = products, user_balance=user_balance, total = total )


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html")

    else:
        symbol = request.form.get("symbol")


        if not symbol:
            return apology("Please enter valid symbol!")

        stocks = lookup(symbol)

        if not stocks:
            return apology("Symbol does not exist!")

        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("Please enter an integer!")

        if shares < 0:
            return apology("Please enter positive number!")


        user_id = session["user_id"]

        """create a variable and store the amount of money required
        to make purchase of stocks"""
        total_amount = shares * stocks["price"]

        #obtaining user's balance info and store it in a variable
        user_balance = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]

        if user_balance < total_amount:
            return apology("Oops! Unsufficient funds!")
        else:
            #update the users balance info
            db.execute("UPDATE users SET cash = ? WHERE id = ?", user_balance - total_amount, user_id)
            #transaction date
            date = datetime.datetime.now()
            #record the transaction into history table
            db.execute("INSERT INTO history (user_id, shares, symbol, price, date) VALUES (?, ?, ?, ?, ?)", user_id, shares, stocks["symbol"], stocks["price"], date)

            flash('Your purchase was successful!')
            return redirect("/")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id = session["user_id"]
    history = db.execute("SELECT symbol, shares, price, date FROM history WHERE user_id = ? ORDER by id", user_id)
    return render_template("history.html", history=history)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "GET":
        return render_template("quote.html")

    else:
        symbol = request.form.get("symbol")

        #checking if the user does not cooperate
        if not symbol:
            return apology("Please enter valid symbol!")

        stocks = lookup(symbol)

        if not stocks:
            return apology("Symbol does not exist!")

        return render_template("quoted.html", name = stocks["name"], price = stocks["price"], symbol = stocks["symbol"])



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if (request.method == "POST"):
        username = request.form.get('username')
        password = request.form.get('password')
        confirmation = request.form.get('confirmation')

        if not username:
            return apology('Please enter valid username!')
        elif not password:
            return apology ('Please type valid password!')
        elif not confirmation:
            return apology ('Please confirm your password!')
        elif password != confirmation:
            return apology ('Passwords do not match')

        hash = generate_password_hash(password)


        #record user data into database
        try:
            newuser = db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hash)
        except:
            return apology('Username already exists! Please try another username!')

        session["user_id"] = newuser
        #showing message on top of page if the user successfully registered
        flash('Done! You are registered and logged in!')
        #redirecting to route
        return redirect("/")

    else:
        return render_template("register.html")



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""


    if request.method == "GET":
        user_id = session["user_id"]
        symbols = db.execute("SELECT symbol FROM history WHERE user_id = ? GROUP BY symbol", user_id)
        return render_template("sell.html", symbols=symbols)

    else:
        user_id = session["user_id"]
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))

        if not symbol:
            return apology("Please enter valid symbol!")

        stocks = lookup(symbol)

        if not stocks:
            return apology("Symbol does not exist!")

        if shares < 0:
            return apology("Please enter valid number of shares!")

        """create a variable and store the amount of money required
        to make purchase of stocks"""
        total_amount = shares * stocks["price"]

        user_shares = db.execute("SELECT SUM(shares) AS shares FROM history WHERE user_id = ? AND symbol = ? GROUP BY symbol", user_id, symbol)[0]["shares"]
        if shares > user_shares:
            return apology("You do not own that amount of shares!")

        # obtaining user's balance info and store it in a variable
        user_balance = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]

        # update the users balance info
        db.execute("UPDATE users SET cash = ? WHERE id = ?", user_balance + total_amount, user_id)
        # transaction date
        date = datetime.datetime.now()
        # record the transaction into history table
        db.execute("INSERT INTO history (user_id, shares, symbol, price, date) VALUES (?, ?, ?, ?, ?)",
                user_id, (-1)*shares, stocks["symbol"], stocks["price"], date)

        flash('Trade was successful!')
        return redirect("/")

"""Adding cash to balance"""
@app.route("/addcash", methods=["GET", "POST"])
@login_required
def addcash():
    """Add cash to balance"""
    if request.method == "GET":
        return render_template("addcash.html")

    else:
        #obtaining the addcash from html, casting float type and storing it in a variable
        addcash = float(request.form.get("addcash"))

        #if the amount is not entered by user return apology message
        if not addcash:
            return apology("Please enter an amount!")

        #checking if the user enter a negative value
        if addcash < 0:
            return apology("Please enter positive number!")

        user_id = session["user_id"]

        # obtaining user's balance info and store it in a variable
        user_balance = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]

        # update the users balance info
        db.execute("UPDATE users SET cash = ? WHERE id = ?", user_balance + addcash, user_id)

        #showing a message if the addcash operation was successful
        flash('Your balance was successfully increased!')
        return redirect("/")







