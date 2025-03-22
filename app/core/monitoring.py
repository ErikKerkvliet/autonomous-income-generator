# app/core/monitoring.py
"""
Monitoring System for the Autonomous Income Generator

This module provides monitoring capabilities for tracking application
performance, income generation, and errors.
"""
import logging
import os
from datetime import datetime
import threading
import time
import json
from typing import Dict, Any, List, Optional
import sqlite3
from flask import Flask, jsonify, render_template_string
import threading


class MonitoringSystem:
    """
    Monitoring system that tracks application performance, income, and errors.
    """

    def __init__(self, db_path: str = "monitoring.db", enable_web: bool = True, web_port: int = 8080):
        """
        Initialize the monitoring system.

        Args:
            db_path: Path to the SQLite database file
            enable_web: Whether to enable the web interface
            web_port: Port for the web interface
        """
        self.db_path = db_path
        self.enable_web = enable_web
        self.web_port = web_port
        self.metrics = {}
        self.income_records = []
        self.active_strategies = set()
        self.last_update = datetime.now()

        # Set up logging
        self._setup_logging()

        # Initialize database
        self._init_database()

        # Start web interface if enabled
        if enable_web:
            self._start_web_interface()

    def _setup_logging(self) -> None:
        """
        Set up logging for the application.
        """
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # Create file handler for detailed logs
        file_handler = logging.FileHandler(
            f"{log_dir}/{datetime.now().strftime('%Y-%m-%d')}.log"
        )
        file_handler.setLevel(logging.DEBUG)

        # Create console handler for important logs
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # Create formatters
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )

        file_handler.setFormatter(file_formatter)
        console_handler.setFormatter(console_formatter)

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)

        self.logger = logging.getLogger(__name__)
        self.logger.info("Monitoring system initialized")

    def _init_database(self) -> None:
        """
        Initialize the SQLite database for monitoring data.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create metrics table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            category TEXT,
            name TEXT,
            value REAL
        )
        ''')

        # Create income table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS income (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            strategy TEXT,
            amount REAL,
            currency TEXT,
            description TEXT
        )
        ''')

        # Create events table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            level TEXT,
            source TEXT,
            message TEXT
        )
        ''')

        conn.commit()
        conn.close()

    def _start_web_interface(self) -> None:
        """
        Start the web interface for monitoring.
        """
        app = Flask(__name__)

        @app.route('/')
        def index():
            return render_template_string('''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Autonomous Income Generator - Monitoring</title>
                <meta http-equiv="refresh" content="60">
                <style>
                    body { font-family: Arial, sans-serif; margin: 0; padding: 20px; }
                    h1, h2 { color: #333; }
                    .card { background: #f9f9f9; border-radius: 5px; padding: 15px; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
                    .metric { display: inline-block; margin-right: 20px; margin-bottom: 10px; }
                    .metric-value { font-size: 24px; font-weight: bold; }
                    .metric-label { font-size: 12px; color: #666; }
                    table { width: 100%; border-collapse: collapse; }
                    th, td { text-align: left; padding: 8px; border-bottom: 1px solid #ddd; }
                    th { background-color: #f2f2f2; }
                </style>
                <script>
                    function refreshData() {
                        fetch('/api/data')
                            .then(response => response.json())
                            .then(data => {
                                document.getElementById('total-income').textContent = data.total_income.toFixed(2);
                                document.getElementById('active-strategies').textContent = data.active_strategies.join(', ');
                                document.getElementById('last-update').textContent = data.last_update;

                                // Update income table
                                const incomeTable = document.getElementById('income-table');
                                incomeTable.innerHTML = '';
                                data.income_records.forEach(record => {
                                    const row = document.createElement('tr');
                                    row.innerHTML = `
                                        <td>${record.timestamp}</td>
                                        <td>${record.strategy}</td>
                                        <td>${record.amount.toFixed(2)} ${record.currency}</td>
                                        <td>${record.description}</td>
                                    `;
                                    incomeTable.appendChild(row);
                                });

                                // Schedule next refresh
                                setTimeout(refreshData, 5000);
                            });
                    }

                    document.addEventListener('DOMContentLoaded', refreshData);
                </script>
            </head>
            <body>
                <h1>Autonomous Income Generator - Monitoring</h1>

                <div class="card">
                    <h2>Overview</h2>
                    <div class="metric">
                        <div class="metric-value">$<span id="total-income">0.00</span></div>
                        <div class="metric-label">Total Income</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value" id="active-strategies">None</div>
                        <div class="metric-label">Active Strategies</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value" id="last-update"></div>
                        <div class="metric-label">Last Update</div>
                    </div>
                </div>

                <div class="card">
                    <h2>Income Records</h2>
                    <table>
                        <thead>
                            <tr>
                                <th>Timestamp</th>
                                <th>Strategy</th>
                                <th>Amount</th>
                                <th>Description</th>
                            </tr>
                        </thead>
                        <tbody id="income-table">
                        </tbody>
                    </table>
                </div>
            </body>
            </html>
            ''')

        @app.route('/api/data')
        def api_data():
            # Fetch data from the database
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get total income
            cursor.execute("SELECT SUM(amount) as total FROM income")
            total_income = cursor.fetchone()['total'] or 0

            # Get income records
            cursor.execute(
                "SELECT * FROM income ORDER BY timestamp DESC LIMIT 10"
            )
            income_records = [dict(row) for row in cursor.fetchall()]

            conn.close()

            return jsonify({
                'total_income': total_income,
                'active_strategies': list(self.active_strategies),
                'income_records': income_records,
                'last_update': self.last_update.strftime("%Y-%m-%d %H:%M:%S")
            })

        # Run Flask in a separate thread
        threading.Thread(
            target=app.run,
            kwargs={'host': '0.0.0.0', 'port': self.web_port, 'debug': False},
            daemon=True
        ).start()

        self.logger.info(f"Web monitoring interface started on port {self.web_port}")

    def record_metric(self, category: str, name: str, value: float) -> None:
        """
        Record a metric for monitoring.

        Args:
            category: Metric category
            name: Metric name
            value: Metric value
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Update in-memory metrics
        if category not in self.metrics:
            self.metrics[category] = {}
        self.metrics[category][name] = value
        self.last_update = datetime.now()

        # Save to database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO metrics (timestamp, category, name, value) VALUES (?, ?, ?, ?)",
            (timestamp, category, name, value)
        )
        conn.commit()
        conn.close()

        self.logger.debug(f"Recorded metric: {category}.{name} = {value}")

    def record_income(self, strategy: str, amount: float, currency: str, description: str) -> None:
        """
        Record an income transaction.

        Args:
            strategy: Income generation strategy
            amount: Amount earned
            currency: Currency code (USD, EUR, etc.)
            description: Description of the income source
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Update in-memory records
        self.income_records.append({
            'timestamp': timestamp,
            'strategy': strategy,
            'amount': amount,
            'currency': currency,
            'description': description
        })
        self.last_update = datetime.now()

        # Add to active strategies
        self.active_strategies.add(strategy)

        # Save to database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO income (timestamp, strategy, amount, currency, description) VALUES (?, ?, ?, ?, ?)",
            (timestamp, strategy, amount, currency, description)
        )
        conn.commit()
        conn.close()

        self.logger.info(f"Income recorded: {amount} {currency} from {strategy} - {description}")

    def record_event(self, level: str, source: str, message: str) -> None:
        """
        Record an application event.

        Args:
            level: Event level (info, warning, error)
            source: Event source (component name)
            message: Event message
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Save to database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO events (timestamp, level, source, message) VALUES (?, ?, ?, ?)",
            (timestamp, level, source, message)
        )
        conn.commit()
        conn.close()

        # Log the event with the appropriate level
        if level.lower() == 'error':
            self.logger.error(f"{source}: {message}")
        elif level.lower() == 'warning':
            self.logger.warning(f"{source}: {message}")
        else:
            self.logger.info(f"{source}: {message}")

    def get_income_summary(self) -> Dict[str, Any]:
        """
        Get a summary of income generation.

        Returns:
            Dictionary with income summary information
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get total income by strategy
        cursor.execute(
            "SELECT strategy, SUM(amount) as total FROM income GROUP BY strategy"
        )
        by_strategy = {row['strategy']: row['total'] for row in cursor.fetchall()}

        # Get total income by currency
        cursor.execute(
            "SELECT currency, SUM(amount) as total FROM income GROUP BY currency"
        )
        by_currency = {row['currency']: row['total'] for row in cursor.fetchall()}

        # Get total income
        cursor.execute("SELECT SUM(amount) as total FROM income")
        total = cursor.fetchone()['total'] or 0

        conn.close()

        return {
            'total': total,
            'by_strategy': by_strategy,
            'by_currency': by_currency
        }