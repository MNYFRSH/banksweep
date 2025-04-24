from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Plaid v30+ imports
from plaid.api import plaid_api
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.country_code import CountryCode
from plaid.configuration import Configuration
from plaid.api_client import ApiClient
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.accounts_balance_get_request import AccountsBalanceGetRequest


# Flask app
app = Flask(__name__)
app.secret_key = 'super_secret_key'

# Setup Plaid client
configuration = Configuration(
    host="https://sandbox.plaid.com",
    api_key={
        'clientId': os.getenv("PLAID_CLIENT_ID"),
        'secret': os.getenv("PLAID_SECRET"),
    }
)

api_client = ApiClient(configuration)
plaid_client = plaid_api.PlaidApi(api_client)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('dashboard.html')


@app.route('/sweep-rules', methods=['GET', 'POST'])
def sweep_rules():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        threshold = float(request.form['threshold'])
        frequency = request.form['frequency']
        session['sweep_rule'] = {
            'threshold': threshold,
            'frequency': frequency
        }
        return redirect(url_for('dashboard'))
    
    return render_template('sweep_rules.html')



@app.route('/simulate_sweep')
def simulate_sweep():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    access_token = session.get('access_token')
    if not access_token:
        return jsonify({'error': 'No access token found.'})

    try:
        balance_request = AccountsBalanceGetRequest(access_token=access_token)
        balance_response = plaid_client.accounts_balance_get(balance_request)

        # Get custom rule or use default
        rule = session.get('sweep_rule')
        threshold = rule.get('threshold') if rule else 20

        sweepable_accounts = []
        for acct in balance_response['accounts']:
            available = acct['balances'].get('available')
            if available and available > threshold:
                sweepable_accounts.append({
                    'name': acct['name'],
                    'available_balance': available,
                    'sweep_amount': 5.00
                })

        return jsonify({
            'sweep_summary': sweepable_accounts
        })

    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/link')
def link():
    return render_template('link.html')

@app.route('/create_link_token', methods=['POST'])
def create_link_token():
    request_data = LinkTokenCreateRequest(
        user=LinkTokenCreateRequestUser(client_user_id='user-123'),
        client_name='BankSweep',
        products=[Products('auth'), Products('transactions')],
        country_codes=[CountryCode('US')],
        language='en'
    )
    response = plaid_client.link_token_create(request_data)
    return jsonify(response.to_dict())

@app.route('/exchange_public_token', methods=['POST'])
def exchange_public_token():
    public_token = request.json.get('public_token')
    try:
        exchange_request = ItemPublicTokenExchangeRequest(public_token=public_token)
        exchange_response = plaid_client.item_public_token_exchange(exchange_request)
        access_token = exchange_response['access_token']

        # Store token in session (or DB later)
        session['access_token'] = access_token

        return jsonify({'message': 'Token exchange successful!'})
    except Exception as e:
        return jsonify({'error': str(e)})
    
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Store credentials in session (mock user DB)
        session['user'] = {
            'username': username,
            'password': password
        }
        return redirect(url_for('dashboard'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = session.get('user')
        if user and user['username'] == username and user['password'] == password:
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            return 'Invalid credentials', 401

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)
