#!/usr/bin/env python3
from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
import sqlite3
import os
import json
from datetime import datetime

app = Flask(__name__, static_folder=None)
CORS(app)  # Enable CORS for React frontend

# Configuration
BUILD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dist')
DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tasks.db')

# Ensure BUILD_DIR is an absolute path
os.makedirs(BUILD_DIR, exist_ok=True)
print(f"Serving static files from: {BUILD_DIR}")

# Database setup
def init_database():
    """Initialize the SQLite database with tasks table"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_detail TEXT NOT NULL,
            task_status TEXT NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def get_db_connection():
    """Get database connection with row factory for dict-like access"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# REST API Endpoints

@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    """Get all tasks"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Optional filtering by status
        status = request.args.get('status')
        if status:
            cursor.execute('SELECT * FROM tasks WHERE task_status = ? ORDER BY id DESC', (status,))
        else:
            cursor.execute('SELECT * FROM tasks ORDER BY id DESC')
        
        tasks = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return jsonify({
            'success': True,
            'data': tasks,
            'count': len(tasks)
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/tasks/<int:task_id>', methods=['GET'])
def get_task(task_id):
    """Get a specific task by ID"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
        task = cursor.fetchone()
        conn.close()
        
        if task:
            return jsonify({
                'success': True,
                'data': dict(task)
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Task not found'
            }), 404
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/tasks', methods=['POST'])
def create_task():
    """Create a new task"""
    try:
        data = request.get_json()
        
        if not data or 'task_detail' not in data:
            return jsonify({
                'success': False,
                'error': 'task_detail is required'
            }), 400
        
        task_detail = data['task_detail'].strip()
        task_status = data.get('task_status', 'pending').strip()
        
        if not task_detail:
            return jsonify({
                'success': False,
                'error': 'task_detail cannot be empty'
            }), 400
        
        # Validate task_status
        valid_statuses = ['pending', 'in_progress', 'completed', 'cancelled']
        if task_status not in valid_statuses:
            return jsonify({
                'success': False,
                'error': f'task_status must be one of: {", ".join(valid_statuses)}'
            }), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO tasks (task_detail, task_status)
            VALUES (?, ?)
        ''', (task_detail, task_status))
        
        task_id = cursor.lastrowid
        conn.commit()
        
        # Get the created task
        cursor.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
        new_task = dict(cursor.fetchone())
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Task created successfully',
            'data': new_task
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    """Update an existing task"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body is required'
            }), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if task exists
        cursor.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
        existing_task = cursor.fetchone()
        
        if not existing_task:
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Task not found'
            }), 404
        
        # Prepare update fields
        update_fields = []
        update_values = []
        
        if 'task_detail' in data:
            task_detail = data['task_detail'].strip()
            if not task_detail:
                conn.close()
                return jsonify({
                    'success': False,
                    'error': 'task_detail cannot be empty'
                }), 400
            update_fields.append('task_detail = ?')
            update_values.append(task_detail)
        
        if 'task_status' in data:
            task_status = data['task_status'].strip()
            valid_statuses = ['pending', 'in_progress', 'completed', 'cancelled']
            if task_status not in valid_statuses:
                conn.close()
                return jsonify({
                    'success': False,
                    'error': f'task_status must be one of: {", ".join(valid_statuses)}'
                }), 400
            update_fields.append('task_status = ?')
            update_values.append(task_status)
        
        if not update_fields:
            conn.close()
            return jsonify({
                'success': False,
                'error': 'No valid fields to update'
            }), 400
        
        # Add updated_at timestamp
        update_fields.append('updated_at = CURRENT_TIMESTAMP')
        update_values.append(task_id)
        
        # Execute update
        query = f"UPDATE tasks SET {', '.join(update_fields)} WHERE id = ?"
        cursor.execute(query, update_values)
        conn.commit()
        
        # Get the updated task
        cursor.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
        updated_task = dict(cursor.fetchone())
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Task updated successfully',
            'data': updated_task
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    """Delete a task"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if task exists
        cursor.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
        existing_task = cursor.fetchone()
        
        if not existing_task:
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Task not found'
            }), 404
        
        # Delete the task
        cursor.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Task deleted successfully'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Additional utility endpoints

@app.route('/api/tasks/stats', methods=['GET'])
def get_tasks_stats():
    """Get task statistics"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                task_status,
                COUNT(*) as count
            FROM tasks 
            GROUP BY task_status
        ''')
        
        stats = {row['task_status']: row['count'] for row in cursor.fetchall()}
        
        cursor.execute('SELECT COUNT(*) as total FROM tasks')
        total = cursor.fetchone()['total']
        
        conn.close()
        
        return jsonify({
            'success': True,
            'data': {
                'total': total,
                'by_status': stats
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Serve React Application

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_react_app(path):
    """Serve React application with client-side routing support"""
    # Handle root path
    if path == "":
        return send_from_directory(BUILD_DIR, 'index.html')
    
    # Try to serve the requested file if it exists
    file_path = os.path.join(BUILD_DIR, path)
    if os.path.exists(file_path) and not os.path.isdir(file_path):
        return send_from_directory(BUILD_DIR, path)
    
    # For any other path, serve index.html to support client-side routing
    return send_from_directory(BUILD_DIR, 'index.html')

# Health check endpoint
@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'success': True,
        'message': 'Server is running',
        'timestamp': datetime.now().isoformat()
    }), 200

# Error handlers
@app.errorhandler(404)
def not_found(error):
    if request.path.startswith('/api/'):
        return jsonify({
            'success': False,
            'error': 'API endpoint not found'
        }), 404
    else:
        # For non-API routes, serve React app
        try:
            return send_from_directory(BUILD_DIR, 'index.html')
        except Exception as e:
            app.logger.error(f"Error serving index.html: {str(e)}")
            return jsonify({
                'success': False,
                'error': 'Frontend application not found',
                'build_dir': BUILD_DIR
            }), 500

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500

def create_sample_data():
    """Create some sample tasks for testing"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if we already have data
    cursor.execute('SELECT COUNT(*) as count FROM tasks')
    count = cursor.fetchone()['count']
    
    if count == 0:
        sample_tasks = [
            ('Complete project documentation', 'pending'),
            ('Review code changes', 'in_progress'),
            ('Deploy to production', 'pending'),
            ('Fix reported bugs', 'completed'),
            ('Update user interface', 'in_progress')
        ]
        
        cursor.executemany('''
            INSERT INTO tasks (task_detail, task_status)
            VALUES (?, ?)
        ''', sample_tasks)
        
        conn.commit()
        print("Sample data created!")
    
    conn.close()

if __name__ == '__main__':
    # Initialize database
    init_database()
    
    # Create sample data (optional)
    create_sample_data()
    
    # Check if build directory exists
    if not os.path.exists(BUILD_DIR):
        print(f"Warning: React build directory '{BUILD_DIR}' not found!")
        print("Make sure to run 'npm run build' in your React project first.")
    
    print("Starting Flask server...")
    print("API endpoints available at:")
    print("  GET    /api/tasks           - Get all tasks")
    print("  GET    /api/tasks/<id>      - Get specific task")
    print("  POST   /api/tasks           - Create new task")
    print("  PUT    /api/tasks/<id>      - Update task")
    print("  DELETE /api/tasks/<id>      - Delete task")
    print("  GET    /api/tasks/stats     - Get task statistics")
    print("  GET    /api/health          - Health check")
    print()
    
    app.run(debug=True, host='0.0.0.0', port=5000)
