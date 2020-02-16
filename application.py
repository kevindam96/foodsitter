import os
import random

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, jsonify
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import error, login_required

import datetime

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///foodsitter.db")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure a username was entered
        if not request.form.get("username"):
            return error(400, "You forgot to provide a username!")

        # Ensure a password was entered
        if not request.form.get("password"):
            return error(400, "You forgot to provide a password!")

        # Ensure a password confirmation was entered
        if not request.form.get("confirmation"):
            return error(400, "You forgot to provide a password confirmation!")

        # Ensure that password and confirmation match
        if request.form.get("password") != request.form.get("confirmation"):
            return error(400, "The password and the confirmation don't match!")

        # Username entered and passwords match, store the values
        username = request.form.get("username")
        password = request.form.get("password")

        # Passwords match, so create the hash
        # Borrowing from: http://werkzeug.pocoo.org/docs/0.12/utils/#werkzeug.security.generate_password_hash)
        pass_hash = generate_password_hash(password, method='pbkdf2:sha256', salt_length=8)

        # Check to see if username already exists and insert the user into the database
        if not db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", username=username, hash=pass_hash):
            return error(400, "Sorry, that username already exists!")

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=username)

        # Log in user automatically upon successful registration:
        # First, remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Define the default categories and locations
        categories = ["Meat", "Fruit", "Vegetable", "Grain", "Beverage", "Entrée", "Side", "Leftovers"]
        locations = ["Refrigerator", "Pantry", "Cupboard", "Countertop"]

        # Store the default categories in the user's account
        for category in categories:
            if not db.execute("INSERT INTO settings (id, name, type) VALUES (:user_id, :name, :type)", user_id = session["user_id"], name = category, type = "category"):
                return error(400, "Sorry, we failed to add the default categories to your account!")

        # Store the default locations in the user's account
        for location in locations:
            if not db.execute("INSERT INTO settings (id, name, type) VALUES (:user_id, :name, :type)", user_id = session["user_id"], name = location, type = "location"):
                return error(400, "Sorry, we failed to add the default locations to your account!")

        # Store the default shopping list configurations in the user's account
        # TODO

        # Redirect user to the homepage
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return error(400, "You forgot to provide a username!")

        # Ensure password was submitted
        elif not request.form.get("password"):
            return error(400, "You forgot to provide a password!")

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return error(400, "You entered an invalid username and/or password!")

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


@app.route("/")
@login_required
def index():
    '''
    Route for the user to display the food currently in the kitchen
    '''
    # Query database to obtain the total quantity of every unique (food, expiration date) pair
    rows = db.execute("SELECT SUM(quantity), unit, food, category, location, expire FROM history WHERE id = :user_id GROUP BY food, expire, location, category HAVING SUM(quantity) != 0", user_id = session["user_id"])
    # Convert the sum of quantity into a string for concatenation with the unit string
    for row in rows:
        row["SUM(quantity)_str"] = str(row["SUM(quantity)"])
        row["date_key"] = datetime.datetime.strptime(row["expire"], "%A (%B %d, %Y)").strftime("%Y%m%d")
    return render_template("index.html", rows = rows)


@app.route("/add", methods=["GET", "POST"])
@login_required
def add():
    '''
    Route for the user to add food to the kitchen
    '''
    # User reached route via a POST request (as by submitting a form via POST)
    if request.method == "POST":
        ### Check if fields were entered ###
        # Check food
        if not request.form.get("food") and not request.form.get("alt_food"):
            return error(400, "You forgot to enter the food you would like to add!")
        # Check quantity
        if not request.form.get("quantity"):
            return error(400, "You forgot to enter the quantity of the food you would like to add!")
        # Check unit
        if not request.form.get("unit") and not request.form.get("alt_unit"):
            return error(400, "You forgot to enter the unit of measure!")
        # Check category
        if not request.form.get("category") and not request.form.get("alt_category"):
            return error(400, "You forgot to enter a category!")
        # Check location
        if not request.form.get("location") and not request.form.get("alt_location"):
            return error(400, "You forgot to enter the location!")
        # Check expiration date
        if not request.form.get("expire"):
            return error(400, "You forgot to enter the expiration date!")
        # Check if quantity entered by user is non-zero and positive
        if float(request.form.get("quantity")) < 0:
            return error(400, "You entered an invalid quantity!")
        # Check if date entered is as recent or later than the current date
        if datetime.datetime.strptime(request.form.get("expire"), "%Y-%m-%d").date() < datetime.date.today():
            return error(400, "You entered an invalid expiration date! Try entering a date that is later than or as late as today!")

        ### Checks complete. Record the add in "history". ###
        # Retrieve food input (if alt_food is empty)
        if not request.form.get("alt_food"):
            food = request.form.get("food")
        # Else, use the food input from the alt_food field
        else:
            food = request.form.get("alt_food")
            food = food.capitalize()

        # Retrieve quantity and unit
        quantity = request.form.get("quantity")

        # Retrieve unit input (if alt_unit is empty)
        if not request.form.get("alt_unit"):
            unit = request.form.get("unit")
        # Else, add the unit into the user's settings and use the unit input from the alt_unit field
        else:
            unit = request.form.get("alt_unit")
            if not db.execute("INSERT INTO settings (id, name, type) VALUES (:user_id, :name, :type)", user_id = session["user_id"], name = unit, type = "unit"):
                return error(400, "Sorry, we failed to add your new unit!")

        # Retrieve category input (if alt_category is empty)
        if not request.form.get("alt_category"):
            category = request.form.get("category")
            category = category.capitalize()
        # Else, add the category to the user's category list and use it for the food add
        else:
            category = request.form.get("alt_category")
            category = category.capitalize()
            if not db.execute("INSERT INTO settings (id, name, type) VALUES (:user_id, :name, :type)", user_id = session["user_id"], name = category, type = "category"):
                return error(400, "Sorry, we failed to add your new category!")

        # Retrieve location input (if alt_location is empty)
        if not request.form.get("alt_location"):
            location = request.form.get("location")
            location = location.capitalize()
        # Else, add the location to the user's location list and use it for the food add
        else:
            location = request.form.get("alt_location")
            location = location.capitalize()
            if not db.execute("INSERT INTO settings (id, name, type) VALUES (:user_id, :name, :type)", user_id = session["user_id"], name = location, type = "location"):
                return error(400, "Sorry, we failed to add your new location!")

        # Obtain the expiration date and reformat it to, for example, Saturday (December 22, 2018)
        expire = datetime.datetime.strptime(request.form.get("expire"), "%Y-%m-%d").strftime("%A (%B %d, %Y)")

        # Obtain current time
        now = datetime.datetime.now()

        # Execute SQL command to record the add in "history" table, also check to see if the command executed properly
        if not db.execute("INSERT INTO history (id, quantity, unit, food, category, location, expire, date_added) VALUES (:user_id, :quantity, :unit, :food, :category, :location, :expire, :now)", user_id = session["user_id"], quantity = quantity, unit = unit, food = food, category = category, location = location, expire = expire, now = now):
            return error(400, "Sorry, we failed to add your food!")

        # Generate a random flash message for confirmation to flash after redirecting the user
        add_confirms = {"Bon appétit!", "Is it time to eat yet?", "Did you hear that? Sorry, that was my stomach...", "Looks tasty!", "Your kitchen thanks you!", "Is your refrigerator running?"}
        messages = random.sample(add_confirms, 1)
        for message in messages:
            flash("Food has been added! " + "(" + str(message) + ")")

        # Redirect user to index
        return redirect("/")

    # User reached route via a GET request (as by clicking a link)
    else:
        # Query the database for the food in the user's kitchen already
        foods = db.execute("SELECT SUM(quantity), food FROM history WHERE id = :user_id GROUP BY food ORDER BY food ASC", user_id = session["user_id"])
        # Query the database for user's custom unit settings
        units = db.execute("SELECT name FROM settings WHERE id = :user_id AND type = :type", user_id = session["user_id"], type = "unit")
        # Query the database for the user's category settings
        categories = db.execute("SELECT name FROM settings WHERE id = :user_id AND type = :type", user_id = session["user_id"], type = "category")
        # Query the database for the user's location settings
        locations = db.execute("SELECT name FROM settings WHERE id = :user_id AND type = :type", user_id = session["user_id"], type = "location")
        return render_template("add.html", foods = foods, units = units, categories = categories, locations = locations)

@app.route("/takeout", methods=["GET", "POST"])
@login_required
def takeout():
    '''
    Route for the user to remove food from the kitchen
    '''
    # User reached route via a POST request (that is, by submitting a form)
    if request.method == "POST":
        # Query database to obtain the total quantity of every unique (food, expiration date) pair
        rows = db.execute("SELECT SUM(quantity), unit, food, category, location, expire FROM history WHERE id = :user_id GROUP BY food, expire, location, category HAVING SUM(quantity) > 0", user_id = session["user_id"])

        # Check if any fields were entered
        i = 0
        count = 0
        for row in rows:
            if request.form.get("qty_" + str(i)):
                count = count + 1
            i = i + 1
        if i == 0:
            return error(400, "You forgot to provide a quantity to remove for any of your foods!")

        # For the fields entered by the user, ensure that the input does not exceed the quantity they currently have in the
        # kitchen and that the input is greater than zero and positive
        i = 0
        for row in rows:
            # Skip empty fields
            if not request.form.get("qty_" + str(i)):
                i = i + 1
            # Consider filled fields
            else:
                # Check if quantity does not exceed the amount in kitchen
                if float(request.form.get("qty_" + str(i))) > row["SUM(quantity)"]:
                    return error(400, "You tried to remove more than what you have of the food \"{}\"!".format(row["food"]))
                # Check if quantity is non-zero and positive
                elif float(request.form.get("qty_" + str(i))) <= 0:
                    return error(400, "You entered an invalid quantity to remove! Please only enter non-zero, positive numbers for the quantity to be removed.")
                # User entered a valid number. Carry out the food removal
                # Retrieve fields
                quantity = -float(request.form.get("qty_" + str(i)))
                unit = row["unit"]
                food = row["food"]
                category = row["category"]
                location = row["location"]
                expire = row["expire"]
                now = datetime.datetime.now()
                # Insert the food removal into the database
                if not db.execute("INSERT INTO history (id, quantity, unit, food, category, location, expire, date_added) VALUES (:user_id, :quantity, :unit, :food, :category, :location, :expire, :now)", user_id = session["user_id"], quantity = quantity, unit = unit, food = food, category = category, location = location, expire = expire, now = now):
                    return error(400, "Sorry, we failed to remove the food from your kitchen!")
                i = i + 1

        # Generate a random flash message for confirmation to flash after redirecting the user
        remove_confirms = {"Bon appétit!", "Is it time to eat yet?", "Did you hear that? Sorry, that was my stomach...", "Looks tasty!", "Your kitchen thanks you!", "Is your refrigerator running?"}
        messages = random.sample(remove_confirms, 1)
        for message in messages:
            flash("Food has been removed! " + "(" + str(message) + ")")

        # Redirect user to index
        return redirect("/")

    # User reached route via a GET request
    else:
        # Query database to obtain the total quantity of every unique (food, expiration date) pair
        rows = db.execute("SELECT SUM(quantity), unit, food, category, location, expire FROM history WHERE id = :user_id GROUP BY food, expire, location, category HAVING SUM(quantity) > 0", user_id = session["user_id"])
        # Convert the sum of quantity into a string for concatenation with the unit string
        i = 0;
        for row in rows:
            row["SUM(quantity)_str"] = str(row["SUM(quantity)"])
            row["date_key"] = datetime.datetime.strptime(row["expire"], "%A (%B %d, %Y)").strftime("%Y%m%d")
            row["qty_form_name"] = "qty_" + str(i)
            i = i + 1
        return (render_template("takeout.html", rows = rows))


@app.route("/history", methods=["GET"])
@login_required
def history():
    '''
    Route for displaying the history of the user's food adds and removes
    '''
    # Query database to obtain the total quantity of every unique (food, expiration date) pair
    rows = db.execute("SELECT quantity, unit, food, category, location, expire, date_added FROM history WHERE id = :user_id ORDER BY date_added DESC", user_id = session["user_id"])
    # Convert the sum of quantity into a string for concatenation with the unit string
    for row in rows:
        row["quantity_str"] = str(row["quantity"])
        row["date_key"] = datetime.datetime.strptime(row["expire"], "%A (%B %d, %Y)").strftime("%Y%m%d")
    return render_template("history.html", rows = rows)


@app.route("/shoppinglist", methods=["GET"])
@login_required
def shoppinglist():
    '''
    Route for the user to access the shopping list (items that are expiring or running low)
    '''
    # Query the database for foods in the kitchen
    rows = db.execute("SELECT SUM(quantity), quantity, food, expire FROM history WHERE id = :user_id GROUP BY food, expire HAVING SUM(quantity) != 0 ORDER BY food ASC, expire DESC", user_id = session["user_id"])
    # Query the database for the user's shopping list settings
    configs = db.execute("SELECT food, days, quantity FROM shoplistconfig WHERE id = :user_id", user_id = session["user_id"])

    # For each row, test the quantity and expire date against the shopping list configurations. If the configurations are satisfied, add the food to the shopListItems dictionary
    for row in rows:
        for config in configs:
            # Food in the kitchen matches a configured food
            if row["food"] == config["food"]:
                # Convert expiration date to a datetime object and obtain current date time. Perform date arithmetic to obtain the test date
                row["expire"] = datetime.datetime.strptime(row["expire"], "%A (%B %d, %Y)")
                row["latest_expire"] = None
                # Check to see if this food has the latest expiration date
                if row["latest_expire"] == None:
                    row["latest_expire"] = row["expire"]
                if row["latest_expire"] < row["expire"]:
                    # reassign the latest expiration date
                    row["latest_expire"] = row["expire"]

                # Obtain the testDate if applicable
                now = datetime.datetime.now()
                if config["days"] != "":
                    numDays = int(config["days"])
                    testDate = row["latest_expire"] - datetime.timedelta(days=numDays)
                # Artifically make the testDate greater than the current date if there is no configuration
                else:
                    testDate = now + datetime.timedelta(days=1)

                # Test the quantity
                if config["quantity"] != "":
                    if row["SUM(quantity)"] < float(config["quantity"]):
                        # Test the expire date (Case where both quantity and expiration date are satisfied)
                        if now >= testDate:
                            # Quantity is low and expiration date is near
                            row["onList"] = True
                            row["listNote"] = "You're running low, and the expiration date is near!"
                        # Only the quantity is low
                        else:
                            row["onList"] = True
                            row["listNote"] = "You're running low!"
                # Test the expire date (only the date)
                elif now >= testDate:
                    # Only the expiration date is near
                    row["onList"] = True
                    row["listNote"] = "The expiration date is near!"
                # Quantity is not low and expiration date is not near
                else:
                    row["onList"] = False
    return render_template("shoppinglist.html", rows = rows)


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    '''
    Settings route for configuring shopping list and custom units/categories/locations
    '''
    # User reached route via a POST request (that is, by submitting a form)
    if request.method == "POST":
        # Query database for foods in user's kitchen
        rows = db.execute("SELECT SUM(quantity), food, unit FROM history WHERE id = :user_id GROUP BY food ORDER BY food ASC", user_id = session["user_id"])

        # Check if any unit, category, location fields were entered
        filled_field = False
        if request.form.getlist("unit") or request.form.getlist("category") or request.form.getlist("location"):
            filled_field = True
        # Check if any food shopping list fields were entered
        for row in rows:
            row["days_form_name"] = "days_" + row["food"]
            row["qty_form_name"] = "qty_" + row["food"]
            if filled_field == False:
                if request.form.get(row["days_form_name"]) or request.form.get(row["qty_form_name"]):
                    filled_field = True
        # Return an error if no fields were filled
        if filled_field == False:
            return error(400, "You forgot to enter a field to tell us which setting you would like to configure!")

        # Remove units, if applicable
        if request.form.getlist("unit"):
            units = request.form.getlist("unit")
            for unit in units:
                db.execute("DELETE FROM settings WHERE id = :user_id AND type = :type AND name = :name", user_id = session["user_id"], type = "unit", name = unit)

        # Remove categories, if applicable
        if request.form.getlist("category"):
            categories = request.form.getlist("category")
            for category in categories:
                db.execute("DELETE FROM settings WHERE id = :user_id AND type = :type AND name = :name", user_id = session["user_id"], type = "category", name = category)

        # Remove locations, if applicable
        if request.form.getlist("location"):
            locations = request.form.getlist("location")
            for location in locations:
                db.execute("DELETE FROM settings WHERE id = :user_id AND type = :type AND name = :name", user_id = session["user_id"], type = "location", name = locations)

        # Query database for already configured foods
        shops = db.execute("SELECT food, days, quantity FROM shoplistconfig WHERE id = :user_id", user_id = session["user_id"])
        # Configure foods, if applicable
        for row in rows:
            # Check if the food is already in shoplistconfig
            configured = False
            for shop in shops:
                if row["food"] == shop["food"]:
                    configured = True
            # Food is not configured. Add a new entry into the shoplistconfig table
            if configured == False:
                food = row["food"]
                days = request.form.get(row["days_form_name"])
                quantity = request.form.get(row["qty_form_name"])
                if days or quantity:
                    db.execute("INSERT INTO shoplistconfig (id, food, days, quantity) VALUES (:user_id, :food, :days, :quantity)", user_id = session["user_id"], food = food, days = days, quantity = quantity)
            # Food is configured. Update the entry in the shoplistconfig table
            else:
                food = row["food"]
                days = request.form.get(row["days_form_name"])
                quantity = request.form.get(row["qty_form_name"])
                db.execute("UPDATE shoplistconfig SET days = :days, quantity = :quantity WHERE id = :user_id AND food = :food", days = days, quantity = quantity, user_id = session["user_id"], food = food)
        flash("Settings updated!")
        return redirect("/settings")

    # User reached route via a GET request (that is, by clicking a link)
    else:
        # Query the database for the food in the user's kitchen already
        rows = db.execute("SELECT SUM(quantity), food, unit FROM history WHERE id = :user_id GROUP BY food ORDER BY food ASC", user_id = session["user_id"])
        # Query the database for user's shopping list settings
        shops = db.execute("SELECT food, days, quantity FROM shoplistconfig WHERE id = :user_id", user_id = session["user_id"])

        # in "rows", store whether that food is configured and the form names for the settings.html form
        for row in rows:
            for shop in shops:
                if row["food"] == shop["food"]:
                    row["configured"] = True
                    row["days_config"] = shop["days"]
                    row["quantity_config"] = shop["quantity"]
                    break
                else:
                    row["configured"] = False
                    row["days_config"] = None
                    row["quantity_config"] = None
            row["days_form_name"] = "days_" + row["food"]
            row["qty_form_name"] = "qty_" + row["food"]
        # Query the database for user's custom unit settings
        units = db.execute("SELECT name FROM settings WHERE id = :user_id AND type = :type", user_id = session["user_id"], type = "unit")
        # Query the database for the user's category settings
        categories = db.execute("SELECT name FROM settings WHERE id = :user_id AND type = :type", user_id = session["user_id"], type = "category")
        # Query the database for the user's location settings
        locations = db.execute("SELECT name FROM settings WHERE id = :user_id AND type = :type", user_id = session["user_id"], type = "location")
        return render_template("settings.html", rows = rows, shops = shops, units = units, categories = categories, locations = locations)


@app.route("/clear", methods=["POST"])
@login_required
def clear():
    '''
    Clear shopping list settings for a food
    '''
    # User reached route via a POST request (that is, by clicking a button)
    if request.method == "POST":
        # Query database for configured foods in the user's settings
        rows = db.execute("SELECT food FROM shoplistconfig WHERE id = :user_id", user_id = session["user_id"])
        # Parse through foods and find a food that matches the button the user clicked. Then, delete the setting
        food = request.form["clear"]
        for row in rows:
            if row["food"] == food:
                # Perform the delete
                if not db.execute("DELETE FROM shoplistconfig WHERE id = :user_id AND food = :food", user_id = session["user_id"], food = food):
                    return error(400, "Sorry, we failed to clear your shopping list settings!")
        flash("Cleared!")
        return redirect("/settings")
