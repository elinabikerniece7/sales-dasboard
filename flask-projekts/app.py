from flask import Flask, render_template, request, jsonify, send_file
from sqlalchemy import create_engine, Column, Integer, String, Float, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timedelta
import json
from random import choice, randint, uniform
import io
import csv
import os

app = Flask(__name__)

# Database setup
Base = declarative_base()
engine = create_engine('sqlite:///data.db')
Session = sessionmaker(bind=engine)

# File paths
SALES_FILE = 'sales_data.csv'
CATEGORIES_FILE = 'categories.json'
REGIONS_FILE = 'regions.json'

class Sales(Base):
    __tablename__ = 'sales'
    id = Column(Integer, primary_key=True)
    category = Column(String)
    amount = Column(Float)
    date = Column(Date)
    region = Column(String)
    product = Column(String)

def init_db():
    Base.metadata.create_all(engine)
    session = Session()
    
    # Clear existing data
    session.query(Sales).delete()
    
    # Load categories from JSON file
    categories = load_categories()
    regions = load_regions()
    
    # Generate sample data
    # Generate dates for the last year
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)
    
    sample_data = []
    for _ in range(100):
        category = choice(categories)
        region = choice(regions)
        amount = round(uniform(10, 1000), 2)
        date = start_date + timedelta(days=randint(0, 365))
        product = f"Product {randint(1, 100)}"  # Generic product names
        
        sample_data.append({
            'category': category,
            'amount': amount,
            'date': date,
            'region': region,
            'product': product
        })
    
    # Insert sample data
    for data in sample_data:
        sale = Sales(**data)
        session.add(sale)
    
    session.commit()
    session.close()

# Initialize categories and regions if files don't exist
def initialize_settings():
    if not os.path.exists(CATEGORIES_FILE):
        with open(CATEGORIES_FILE, 'w') as f:
            json.dump(['Elektronika', 'Apģērbs', 'Pārtika', 'Mēbeles'], f)
    if not os.path.exists(REGIONS_FILE):
        with open(REGIONS_FILE, 'w') as f:
            json.dump(['Rīga', 'Daugavpils', 'Liepāja', 'Jelgava', 'Ventspils'], f)

# Load categories and regions
def load_categories():
    with open(CATEGORIES_FILE, 'r') as f:
        return json.load(f)

def load_regions():
    with open(REGIONS_FILE, 'r') as f:
        return json.load(f)

# Save categories and regions
def save_categories(categories):
    with open(CATEGORIES_FILE, 'w') as f:
        json.dump(categories, f)

def save_regions(regions):
    with open(REGIONS_FILE, 'w') as f:
        json.dump(regions, f)

# Initialize settings on startup
initialize_settings()

@app.route('/add_sale', methods=['GET', 'POST'])
def add_sale():
    if request.method == 'POST':
        session = Session()
        try:
            new_sale = Sales(
                category=request.form['category'],
                amount=float(request.form['amount']),
                date=datetime.strptime(request.form['date'], '%Y-%m-%d'),
                region=request.form['region'],
                product=request.form['product']
            )
            session.add(new_sale)
            session.commit()
            session.close()
            return jsonify({'status': 'success'})
        except Exception as e:
            session.rollback()
            session.close()
            return jsonify({'status': 'error', 'message': str(e)})
    
    categories = load_categories()
    regions = load_regions()
    return render_template('add_sale.html', categories=categories, regions=regions)

@app.route('/all_sales')
def all_sales():
    session = Session()
    sales = session.query(Sales).all()
    session.close()
    return render_template('all_sales.html', sales=sales)

@app.route('/')
def index():
    categories = load_categories()
    regions = load_regions()
    return render_template('index.html', categories=categories, regions=regions)

@app.route('/data')
def get_data():
    session = Session()
    category = request.args.get('category', '')
    region = request.args.get('region', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    query = session.query(Sales)
    
    if category:
        query = query.filter(Sales.category == category)
    if region:
        query = query.filter(Sales.region == region)
    if start_date:
        query = query.filter(Sales.date >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(Sales.date <= datetime.strptime(end_date, '%Y-%m-%d'))
    
    data = query.all()
    session.close()
    
    return jsonify([{
        'date': d.date.strftime('%Y-%m-%d'),
        'amount': d.amount,
        'category': d.category,
        'region': d.region,
        'product': d.product
    } for d in data])

@app.route('/charts')
def get_charts():
    session = Session()
    category = request.args.get('category', '')
    region = request.args.get('region', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    query = session.query(Sales)
    
    if category:
        query = query.filter(Sales.category == category)
    if region:
        query = query.filter(Sales.region == region)
    if start_date:
        query = query.filter(Sales.date >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(Sales.date <= datetime.strptime(end_date, '%Y-%m-%d'))
    
    df = pd.read_sql(query.statement, session.bind)
    session.close()
    
    # Prepare data for Chart.js
    
    # Sales by Region
    region_data = df.groupby('region')['amount'].sum().reset_index()
    region_chart = {
        'labels': region_data['region'].tolist(),
        'data': region_data['amount'].tolist()
    }
    
    # Sales by Category
    category_data = df.groupby('category')['amount'].sum().reset_index()
    category_chart = {
        'labels': category_data['category'].tolist(),
        'data': category_data['amount'].tolist()
    }
    
    # Sales Distribution by Category (Pie Chart)
    pie_data = df.groupby('category')['amount'].sum().reset_index()
    pie_chart = {
        'labels': pie_data['category'].tolist(),
        'data': pie_data['amount'].tolist()
    }
    
    return jsonify({
        'region': region_chart,
        'category': category_chart,
        'pie': pie_chart
    })

@app.route('/delete_sale/<int:sale_id>', methods=['POST'])
def delete_sale(sale_id):
    session = Session()
    try:
        sale = session.query(Sales).filter_by(id=sale_id).first()
        if sale:
            session.delete(sale)
            session.commit()
            session.close()
            return jsonify({'status': 'success'})
        else:
            session.close()
            return jsonify({'status': 'error', 'message': 'Sale not found'})
    except Exception as e:
        session.rollback()
        session.close()
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/upload_csv', methods=['GET', 'POST'])
def upload_csv():
    if request.method == 'POST':
        if 'file' not in request.files:
            return jsonify({'status': 'error', 'message': 'No file uploaded'})
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'status': 'error', 'message': 'No file selected'})
        
        if not file.filename.endswith('.csv'):
            return jsonify({'status': 'error', 'message': 'File must be a CSV'})
        
        try:
            # Read CSV file
            df = pd.read_csv(file)
            
            # Validate required columns
            required_columns = ['category', 'amount', 'date', 'region', 'product']
            if not all(col in df.columns for col in required_columns):
                return jsonify({'status': 'error', 'message': 'CSV must contain columns: category, amount, date, region, product'})
            
            # Convert date strings to datetime
            df['date'] = pd.to_datetime(df['date'])
            
            session = Session()
            
            # Insert data
            for _, row in df.iterrows():
                sale = Sales(
                    category=row['category'],
                    amount=float(row['amount']),
                    date=row['date'].date(),
                    region=row['region'],
                    product=row['product']
                )
                session.add(sale)
            
            session.commit()
            session.close()
            
            return jsonify({'status': 'success', 'message': f'Successfully imported {len(df)} records'})
            
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)})
    
    return render_template('upload_csv.html')

@app.route('/download_csv')
def download_csv():
    session = Session()
    sales = session.query(Sales).all()
    session.close()
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['id', 'category', 'amount', 'date', 'region', 'product'])
    
    # Write data
    for sale in sales:
        writer.writerow([
            sale.id,
            sale.category,
            sale.amount,
            sale.date.strftime('%Y-%m-%d'),
            sale.region,
            sale.product
        ])
    
    # Create response
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='sales_data.csv'
    )

@app.route('/analytics')
def get_analytics():
    try:
        session = Session()
        category = request.args.get('category', '')
        region = request.args.get('region', '')
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')
        
        query = session.query(Sales)
        
        if category:
            query = query.filter(Sales.category == category)
        if region:
            query = query.filter(Sales.region == region)
        if start_date:
            query = query.filter(Sales.date >= datetime.strptime(start_date, '%Y-%m-%d'))
        if end_date:
            query = query.filter(Sales.date <= datetime.strptime(end_date, '%Y-%m-%d'))
        
        df = pd.read_sql(query.statement, session.bind)
        session.close()
        
        # Check if DataFrame is empty
        if df.empty:
            return jsonify({
                'stats': {
                    'total_sales': 0,
                    'average_sale': 0,
                    'total_transactions': 0,
                    'unique_products': 0
                },
                'category_stats': {},
                'region_stats': {},
                'top_products': {},
                'monthly_trend': {}
            })
        
        # Basic statistics
        stats = {
            'total_sales': float(df['amount'].sum()),
            'average_sale': float(df['amount'].mean()),
            'total_transactions': int(len(df)),
            'unique_products': int(df['product'].nunique())
        }
        
        # Category analysis
        category_agg = df.groupby('category').agg({
            'amount': ['sum', 'mean', 'count'],
            'product': 'nunique'
        }).round(2)
        
        # Flatten column names for category stats
        category_stats = {}
        for category in category_agg.index:
            category_stats[category] = {
                'total_sales': float(category_agg.loc[category, ('amount', 'sum')]),
                'average_sale': float(category_agg.loc[category, ('amount', 'mean')]),
                'transactions': int(category_agg.loc[category, ('amount', 'count')]),
                'unique_products': int(category_agg.loc[category, ('product', 'nunique')])
            }
        
        # Region analysis
        region_agg = df.groupby('region').agg({
            'amount': ['sum', 'mean', 'count'],
            'category': 'nunique'
        }).round(2)
        
        # Flatten column names for region stats
        region_stats = {}
        for region in region_agg.index:
            region_stats[region] = {
                'total_sales': float(region_agg.loc[region, ('amount', 'sum')]),
                'average_sale': float(region_agg.loc[region, ('amount', 'mean')]),
                'transactions': int(region_agg.loc[region, ('amount', 'count')]),
                'unique_categories': int(region_agg.loc[region, ('category', 'nunique')])
            }
        
        # Top products
        top_products = df.groupby('product')['amount'].sum().nlargest(5).round(2).to_dict()
        
        # Monthly trend
        df['month'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m')
        monthly_trend = df.groupby('month')['amount'].sum().round(2).to_dict()
        
        return jsonify({
            'stats': stats,
            'category_stats': category_stats,
            'region_stats': region_stats,
            'top_products': top_products,
            'monthly_trend': monthly_trend
        })
    except Exception as e:
        return jsonify({
            'error': str(e),
            'stats': {
                'total_sales': 0,
                'average_sale': 0,
                'total_transactions': 0,
                'unique_products': 0
            },
            'category_stats': {},
            'region_stats': {},
            'top_products': {},
            'monthly_trend': {}
        }), 500

@app.route('/settings')
def settings():
    categories = load_categories()
    regions = load_regions()
    return render_template('settings.html', categories=categories, regions=regions)

@app.route('/add_category', methods=['POST'])
def add_category():
    category = request.form.get('category')
    if not category:
        return jsonify({'status': 'error', 'message': 'Kategorija nevar būt tukša'})
    
    categories = load_categories()
    if category in categories:
        return jsonify({'status': 'error', 'message': 'Šāda kategorija jau eksistē'})
    
    categories.append(category)
    save_categories(categories)
    return jsonify({'status': 'success'})

@app.route('/delete_category', methods=['POST'])
def delete_category():
    category = request.form.get('category')
    if not category:
        return jsonify({'status': 'error', 'message': 'Kategorija nav norādīta'})
    
    # Check if there are any sales with this category
    session = Session()
    sales_count = session.query(Sales).filter(Sales.category == category).count()
    session.close()
    
    if sales_count > 0:
        return jsonify({
            'status': 'error', 
            'message': 'Nevar izdzēst kategoriju, jo tai ir piesaistītas pārdošanas. Vispirms izdzēsiet vai pārvietojiet šīs pārdošanas.'
        })
    
    categories = load_categories()
    if category not in categories:
        return jsonify({'status': 'error', 'message': 'Kategorija nav atrasta'})
    
    categories.remove(category)
    save_categories(categories)
    return jsonify({'status': 'success'})

@app.route('/add_region', methods=['POST'])
def add_region():
    region = request.form.get('region')
    if not region:
        return jsonify({'status': 'error', 'message': 'Reģions nevar būt tukšs'})
    
    regions = load_regions()
    if region in regions:
        return jsonify({'status': 'error', 'message': 'Šāds reģions jau eksistē'})
    
    regions.append(region)
    save_regions(regions)
    return jsonify({'status': 'success'})

@app.route('/delete_region', methods=['POST'])
def delete_region():
    region = request.form.get('region')
    if not region:
        return jsonify({'status': 'error', 'message': 'Reģions nav norādīts'})
    
    regions = load_regions()
    if region not in regions:
        return jsonify({'status': 'error', 'message': 'Reģions nav atrasts'})
    
    regions.remove(region)
    save_regions(regions)
    return jsonify({'status': 'success'})

@app.route('/edit_category', methods=['POST'])
def edit_category():
    old_category = request.form.get('old_category')
    new_category = request.form.get('new_category')
    
    if not old_category or not new_category:
        return jsonify({'status': 'error', 'message': 'Kategorija nevar būt tukša'})
    
    categories = load_categories()
    if new_category in categories and new_category != old_category:
        return jsonify({'status': 'error', 'message': 'Šāda kategorija jau eksistē'})
    
    # Update category in database
    session = Session()
    try:
        sales = session.query(Sales).filter(Sales.category == old_category).all()
        for sale in sales:
            sale.category = new_category
        session.commit()
        
        # Update categories list
        categories.remove(old_category)
        categories.append(new_category)
        save_categories(categories)
        
        session.close()
        return jsonify({'status': 'success'})
    except Exception as e:
        session.rollback()
        session.close()
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/edit_region', methods=['POST'])
def edit_region():
    old_region = request.form.get('old_region')
    new_region = request.form.get('new_region')
    
    if not old_region or not new_region:
        return jsonify({'status': 'error', 'message': 'Reģions nevar būt tukšs'})
    
    regions = load_regions()
    if new_region in regions and new_region != old_region:
        return jsonify({'status': 'error', 'message': 'Šāds reģions jau eksistē'})
    
    # Update region in database
    session = Session()
    try:
        sales = session.query(Sales).filter(Sales.region == old_region).all()
        for sale in sales:
            sale.region = new_region
        session.commit()
        
        # Update regions list
        regions.remove(old_region)
        regions.append(new_region)
        save_regions(regions)
        
        session.close()
        return jsonify({'status': 'success'})
    except Exception as e:
        session.rollback()
        session.close()
        return jsonify({'status': 'error', 'message': str(e)})

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
