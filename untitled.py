from flask import Flask, render_template, request, redirect, url_for, flash, jsonify 
app = Flask(__name__)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker 
from database_setup import Base, Restaurant, MenuItem
# new Imports
from flask import session as login_session
import random, string
#sudo random string to indentify session above

#Imports for Oauth
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests

CLIENT_ID = json.loads(open('client_secrets.json', 'r').read())['web']['client_id']


engine = create_engine('sqlite:///restaurantmenu.db')
Base.metadata.bind = engine

DBsession = sessionmaker(bind=engine)
session = DBsession()

@app.route('/')
@app.route('/hello')
def helloworld():
	return "Hello World"

@app.route('/login')
def showLogin():
	state = ''.join(random.choice(string.ascii_uppercase + string.digits) for x in xrange(32))
	login_session['state'] = state
	print state 
	return render_template('login.html', STATE =state)
	#return "the current session state is %s" %login_session['state']

@app.route('/gconnect', methods =['POST'])
def gconnect():
	if request.args.get('state') != login_session['state']:
		print "took the temp state token"
		response = make_response(json.dumps('Invalid state'), 401)
		response.headers['Content-Type'] ='application/json'
		return response
	code = request.data
	try:
		#Upgarding the authorzation code into a credentials Object
		oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
		oauth_flow.redirect_uri='postmessage'
		credentials = oauth_flow.step2_exchange(code)
		print credentials

	except FlowExchangeError:
		response = make_response(json.dumps('Failed to upgrade auth code'), 401)
		response.headers['Contents-Type'] = 'application/json'
		return response
	#check if the access token is valid
	access_token = credentials.access_token
	print "after try catch block"
	print access_token
	url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s' % access_token)
	h = httplib2.Http()
	result = json.loads(h.request(url, 'GET')[1])
	#if there was an error
	if result.get('error') is not None:
		response = make_response(json.dumps(result.get('error')), 50)
		response.header['Content-Type'] = 'application/json'
	#check if get the right access token for the intended purpose
	gplus_id = credentials.id_token['sub']
	if result['user_id'] != gplus_id:
		response = make_response(json.dumps("Tokens user ID does not match"), 401)
		return response
	#verify of the token is for the app 
	if result['issued_to'] != CLIENT_ID:
		response = make_response(json.dumps("Token clinet ID no match"), 401)
		print "Tokens client ID not match"
		response.headers['Content-Type'] ='application/json'
		return response
	#check if the user is laready logged into the system
	stored_credentials = login_session.get('credentials')
	stored_gplus_id = login_session.get('gplus_id')
	if stored_credentials is not None and gplus_id == stored_gplus_id:
		response = make_response(json.dumps('current user is laready logged in'), 200)
		response.headers['Content-Type'] = 'application/json'
	#above if statements later
	login_session['credentials'] = credentials
	login_session['gplus_id'] = gplus_id

	#get user info
	userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
	params = {'access_token': credentials.access_token, 'alt':'json'}
	answer = requests.get(userinfo_url, params=params)
	data = json.loads(answer.text)

	login_session['username'] = data["name"]
	login_session['picture'] = data["picture"]
	login_session['email'] = data["email"]

	output =''
	output +='<h1> Welcome,'
	output += login_session['username']

	output +='!</h1>'
	#output += login_session['picture']
	output += '''<img src="%s" alt=" Hemanth">''' %(login_session['picture'])
	#output += '''style = "width:300px; height:300px;border-radius: 150px; -webkit-border-radius: 150px; -moz-border-radius: 150px;'''
	flash("You are logged in as %s" %login_session['username'])
	return output

@app.route('/gdisconnect')
def gdisconnect():
	#cache is stoting the previous access_toekn in credentials
	#Need a function to clear cache when logging in
	# only disconnect a current user
	credentials = login_session.get('credentials')
	if credentials is None:
		response = make_response(json.dumps('current user not connected'), 401)
		response.headers['Content-Type'] = 'application/json'
		return response

	access_token = credentials.access_token
	print "**************"
	print access_token
	url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % access_token
	#print url
	h = httplib2.Http()
	result = h.request(url, 'GET')[0]
	#print result
	if result['status'] == '200':
		del login_session['credentials']
		del login_session['gplus_id']
		del login_session['email']
		del login_session['picture']
		response = make_response(json.dumps('Disconnected'), 200)
		response.headers['Content-Type'] = 'application/json'
		return response
	else:
		response = make_response(json.dumps('Failed to disconnect'), 400)
		response.headers['Content-Type'] = 'application/json'
		return response

@app.route('/restaurants/')
def restaurants_list():
	restaurants = session.query(Restaurant).all()
	return render_template('restaurants_list.html', restaurants = restaurants)


@app.route('/restaurants/addnewrestaurant', methods =['GET','POST'])
def newrestaurant():
	#newrestaurant = Restaurant()
	#newrestaurant.name = request.form['name']
	return render_template('newRestaurantadd.html')
	return 'new restaurant added'


@app.route('/restaurants/<int:restaurant_id>/')
def restaurants_menu_list(restaurant_id):
	restaurant = session.query(Restaurant).filter_by(id= restaurant_id).one()
	items = session.query(MenuItem).filter_by(restaurant_id = restaurant_id)
	if items is None:
		flash("No items added")
	return render_template('menu.html', restaurant=restaurant, items= items)

#API endpoint
@app.route('/restaurants/<int:restaurant_id>/menu/JSON')
def restaurantMenuJSON(restaurant_id):
	restaurant = session.query(Restaurant).filter_by(id = restaurant_id).one()
	items = session.query(MenuItem).filter_by(restaurant_id=restaurant_id).all()
	return jsonify(MenuItems=[i.serialize for i in items])


@app.route('/restaurants/<int:restaurant_id>/menu/<int:menu_id>/JSON')
def menuItemJSON(restaurant_id, menu_id):
	menu = session.query(MenuItem).filter_by(id = menu_id).one()
	return jsonify(MenuItem = menu.serialize)

@app.route('/restaurants/<int:restaurant_id>/new/', methods= ['GET','POST'])
def newMenuItem(restaurant_id):
	if request.method == 'POST':
		newItem = MenuItem(name = request.form['name'],restaurant_id = restaurant_id, )
		newItem.price = request.form['price']
		newItem.description = request.form['Description']
		newItem.course = request.form['course']
		session.add(newItem)
		session.commit()
		flash("new menu item created")
		return redirect(url_for('restaurants_menu_list',restaurant_id = restaurant_id))
	else:
		return render_template('newmenuitem.html', restaurant_id=restaurant_id)



@app.route('/restaurants/<int:restaurant_id>/<int:menu_id>/edit/', methods = ['GET','POST'])
def editMenuItem(restaurant_id, menu_id):
	editItem = session.query(MenuItem).filter_by(id = menu_id).one()
	print('*'*50)
	if request.method == 'POST':
		if request.form['name']:
			print request.form['name']
			editItem.name = request.form['name']
			editItem.price = request.form['price']
			editItem.description = request.form['Description']
			editItem.course  = request.form['course']
		session.add(editItem)
		session.commit
		flash("Item name changed")
		return redirect(url_for('restaurants_menu_list', restaurant_id= restaurant_id))
	else:
		print('*'*10, menu_id)
		return render_template('editmenuitem.html', restaurant_id = restaurant_id, menu_id = menu_id, i= editItem)


@app.route('/restaurants/<int:restaurant_id>/<int:menu_id>/delete/', methods = ['GET','POST'])
def deleteMenuItem(restaurant_id, menu_id):
	deleteItem = session.query(MenuItem).filter_by(id = menu_id).one()
	if request.method == 'POST':
		session.delete(deleteItem)
		session.commit()
		flash("Item deleted")
		return redirect(url_for('restaurants_menu_list', restaurant_id = restaurant_id))
	else:
		return render_template('deleteItem.html', restaurant_id = restaurant_id, menu_id = menu_id, i = deleteItem)

#   71420721369-9go42k1eji92kan60um0agnl4brukgpk.apps.googleusercontent.com
if __name__ == '__main__':
	app.secret_key = 'Yh6iSItV8H8BDuOEyZ73ZLEL'
	app.debug = True
	app.run(host = '0.0.0.0', port = 5000)
	