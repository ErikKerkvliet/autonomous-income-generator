# app/managers/finance_manager.py
"""
Finance Manager for the Autonomous Income Generator.

This module tracks financial transactions and balances.
"""
import logging
import time
import datetime
from typing import Dict, Any, List, Optional
import json


class FinanceManager:
    """
    Manages financial transactions and balances.
    """

    def __init__(self, db_manager, btc_balance: float = 0.0,
                 amazon_balance: float = 0.0, amazon_currency: str = "EUR"):
        """
        Initialize the finance manager.

        Args:
            db_manager: Database manager instance
            btc_balance: Initial Bitcoin balance in USD
            amazon_balance: Initial Amazon gift card balance
            amazon_currency: Amazon gift card currency
        """
        self.logger = logging.getLogger(__name__)
        self.db_manager = db_manager

        # Initial balances
        self.btc_balance = btc_balance
        self.amazon_balance = amazon_balance
        self.amazon_currency = amazon_currency

        # Initialize database tables
        self._initialize_tables()

        # Load balances from database
        self._load_balances()

        self.logger.info(f"Initialized finance manager with BTC: ${self.btc_balance}, "
                         f"Amazon: {self.amazon_balance} {self.amazon_currency}")

    def _initialize_tables(self) -> None:
        """
        Initialize finance-related database tables.
        """
        # Create transactions table
        self.db_manager.execute("""
            CREATE TABLE IF NOT EXISTS finance_transactions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                timestamp DATETIME,
                transaction_type ENUM('income', 'expense', 'transfer'),
                amount FLOAT,
                currency VARCHAR(10),
                source VARCHAR(255),
                destination VARCHAR(255),
                description TEXT,
                status VARCHAR(50)
            )
        """)

        # Create balances table
        self.db_manager.execute("""
            CREATE TABLE IF NOT EXISTS finance_balances (
                id INT AUTO_INCREMENT PRIMARY KEY,
                account VARCHAR(255),
                balance FLOAT,
                currency VARCHAR(10),
                last_updated DATETIME
            )
        """)

    def _load_balances(self) -> None:
        """
        Load account balances from the database.
        """
        # Load Bitcoin balance
        result = self.db_manager.query(
            "SELECT balance FROM finance_balances WHERE account = 'bitcoin'"
        )

        if result:
            self.btc_balance = result[0]['balance']
        else:
            # Initialize BTC balance in database
            self.db_manager.execute(
                """
                INSERT INTO finance_balances (account, balance, currency, last_updated)
                VALUES (%s, %s, %s, %s)
                """,
                ('bitcoin', self.btc_balance, 'USD', datetime.datetime.now())
            )

        # Load Amazon balance
        result = self.db_manager.query(
            "SELECT balance, currency FROM finance_balances WHERE account = 'amazon'"
        )

        if result:
            self.amazon_balance = result[0]['balance']
            self.amazon_currency = result[0]['currency']
        else:
            # Initialize Amazon balance in database
            self.db_manager.execute(
                """
                INSERT INTO finance_balances (account, balance, currency, last_updated)
                VALUES (%s, %s, %s, %s)
                """,
                ('amazon', self.amazon_balance, self.amazon_currency, datetime.datetime.now())
            )

    def _update_balance(self, account: str, balance: float, currency: str) -> None:
        """
        Update an account balance in the database.

        Args:
            account: Account name
            balance: New balance
            currency: Currency code
        """
        self.db_manager.execute(
            """
            UPDATE finance_balances 
            SET balance = %s, currency = %s, last_updated = %s
            WHERE account = %s
            """,
            (balance, currency, datetime.datetime.now(), account)
        )

    def add_income(self, source: str, amount: float, currency: str = "USD",
                   description: str = "", destination: str = "bitcoin") -> bool:
        """
        Add income to an account.

        Args:
            source: Income source
            amount: Amount
            currency: Currency code
            description: Transaction description
            destination: Destination account (bitcoin or amazon)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Record the transaction
            self.db_manager.execute(
                """
                INSERT INTO finance_transactions 
                (timestamp, transaction_type, amount, currency, source, destination, description, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    datetime.datetime.now(),
                    'income',
                    amount,
                    currency,
                    source,
                    destination,
                    description,
                    'completed'
                )
            )

            # Update the account balance
            if destination.lower() == 'bitcoin':
                # For simplicity, assuming all currencies are converted to USD for Bitcoin
                self.btc_balance += amount
                self._update_balance('bitcoin', self.btc_balance, 'USD')
            elif destination.lower() == 'amazon':
                # For Amazon, maintain the original currency
                if currency == self.amazon_currency:
                    self.amazon_balance += amount
                else:
                    # A real implementation would handle currency conversion
                    # This is a simplified version that assumes the same currency
                    self.logger.warning(f"Currency mismatch for Amazon: {currency} vs {self.amazon_currency}")
                    self.amazon_balance += amount

                self._update_balance('amazon', self.amazon_balance, self.amazon_currency)

            self.logger.info(f"Added income: {amount} {currency} from {source} to {destination}")
            return True

        except Exception as e:
            self.logger.error(f"Error adding income: {str(e)}")
            return False

    def add_expense(self, destination: str, amount: float, currency: str = "USD",
                    description: str = "", source: str = "bitcoin") -> bool:
        """
        Add an expense from an account.

        Args:
            destination: Expense destination
            amount: Amount
            currency: Currency code
            description: Transaction description
            source: Source account (bitcoin or amazon)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if sufficient funds are available
            if source.lower() == 'bitcoin':
                if amount > self.btc_balance:
                    self.logger.error(f"Insufficient Bitcoin balance: {self.btc_balance} < {amount}")
                    return False

                # Record the transaction
                self.db_manager.execute(
                    """
                    INSERT INTO finance_transactions 
                    (timestamp, transaction_type, amount, currency, source, destination, description, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        datetime.datetime.now(),
                        'expense',
                        amount,
                        currency,
                        source,
                        destination,
                        description,
                        'completed'
                    )
                )

                # Update the balance
                self.btc_balance -= amount
                self._update_balance('bitcoin', self.btc_balance, 'USD')

            elif source.lower() == 'amazon':
                if amount > self.amazon_balance:
                    self.logger.error(f"Insufficient Amazon balance: {self.amazon_balance} < {amount}")
                    return False

                # For Amazon, check currency
                if currency != self.amazon_currency:
                    self.logger.error(f"Currency mismatch for Amazon expense: {currency} vs {self.amazon_currency}")
                    return False

                # Record the transaction
                self.db_manager.execute(
                    """
                    INSERT INTO finance_transactions 
                    (timestamp, transaction_type, amount, currency, source, destination, description, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        datetime.datetime.now(),
                        'expense',
                        amount,
                        currency,
                        source,
                        destination,
                        description,
                        'completed'
                    )
                )

                # Update the balance
                self.amazon_balance -= amount
                self._update_balance('amazon', self.amazon_balance, self.amazon_currency)

            self.logger.info(f"Added expense: {amount} {currency} from {source} to {destination}")
            return True

        except Exception as e:
            self.logger.error(f"Error adding expense: {str(e)}")
            return False

    def transfer_funds(self, source: str, destination: str, amount: float,
                       description: str = "") -> bool:
        """
        Transfer funds between accounts.

        Args:
            source: Source account
            destination: Destination account
            amount: Amount to transfer
            description: Transaction description

        Returns:
            True if successful, False otherwise
        """
        try:
            # Currently only supporting transfer from Bitcoin to Amazon in EUR
            # A real implementation would handle more complex transfers and currency conversion

            if source.lower() == 'bitcoin' and destination.lower() == 'amazon':
                if amount > self.btc_balance:
                    self.logger.error(f"Insufficient Bitcoin balance: {self.btc_balance} < {amount}")
                    return False

                # Record the transaction
                self.db_manager.execute(
                    """
                    INSERT INTO finance_transactions 
                    (timestamp, transaction_type, amount, currency, source, destination, description, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        datetime.datetime.now(),
                        'transfer',
                        amount,
                        'USD',  # Bitcoin is in USD
                        source,
                        destination,
                        description,
                        'completed'
                    )
                )

                # Update Bitcoin balance
                self.btc_balance -= amount
                self._update_balance('bitcoin', self.btc_balance, 'USD')

                # Simplified currency conversion (in a real app, this would use exchange rates)
                # For simplicity, we're assuming 1 USD = 0.9 EUR
                eur_amount = amount * 0.9

                # Update Amazon balance
                self.amazon_balance += eur_amount
                self._update_balance('amazon', self.amazon_balance, 'EUR')

                self.logger.info(f"Transferred {amount} USD from Bitcoin to {eur_amount} EUR in Amazon")
                return True

            elif source.lower() == 'amazon' and destination.lower() == 'bitcoin':
                self.logger.error("Transfer from Amazon to Bitcoin is not supported")
                return False

            else:
                self.logger.error(f"Unsupported transfer: {source} to {destination}")
                return False

        except Exception as e:
            self.logger.error(f"Error transferring funds: {str(e)}")
            return False

    def get_transaction_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent transaction history.

        Args:
            limit: Maximum number of transactions to return

        Returns:
            List of transaction dictionaries
        """
        try:
            result = self.db_manager.query(
                """
                SELECT * FROM finance_transactions
                ORDER BY timestamp DESC
                LIMIT %s
                """,
                (limit,)
            )

            return result

        except Exception as e:
            self.logger.error(f"Error getting transaction history: {str(e)}")
            return []

    def get_income_by_source(self, start_date: datetime.datetime = None,
                             end_date: datetime.datetime = None) -> Dict[str, float]:
        """
        Get income grouped by source.

        Args:
            start_date: Start date for filtering (optional)
            end_date: End date for filtering (optional)

        Returns:
            Dictionary of income by source
        """
        try:
            query = """
                SELECT source, SUM(amount) as total
                FROM finance_transactions
                WHERE transaction_type = 'income'
            """

            params = []

            if start_date:
                query += " AND timestamp >= %s"
                params.append(start_date)

            if end_date:
                query += " AND timestamp <= %s"
                params.append(end_date)

            query += " GROUP BY source"

            result = self.db_manager.query(query, tuple(params))

            # Convert to dictionary
            income_by_source = {}
            for row in result:
                income_by_source[row['source']] = row['total']

            return income_by_source

        except Exception as e:
            self.logger.error(f"Error getting income by source: {str(e)}")
            return {}

    def get_total_income(self, start_date: datetime.datetime = None,
                         end_date: datetime.datetime = None) -> float:
        """
        Get total income.

        Args:
            start_date: Start date for filtering (optional)
            end_date: End date for filtering (optional)

        Returns:
            Total income amount
        """
        try:
            query = """
                SELECT SUM(amount) as total
                FROM finance_transactions
                WHERE transaction_type = 'income'
            """

            params = []

            if start_date:
                query += " AND timestamp >= %s"
                params.append(start_date)

            if end_date:
                query += " AND timestamp <= %s"
                params.append(end_date)

            result = self.db_manager.query(query, tuple(params))

            return result[0]['total'] or 0.0

        except Exception as e:
            self.logger.error(f"Error getting total income: {str(e)}")
            return 0.0

    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of financial status.

        Returns:
            Dictionary with financial summary
        """
        try:
            # Get total income
            total_income = self.get_total_income()

            # Get total expenses
            query = "SELECT SUM(amount) as total FROM finance_transactions WHERE transaction_type = 'expense'"
            result = self.db_manager.query(query)
            total_expenses = result[0]['total'] or 0.0

            # Get income by source
            income_by_source = self.get_income_by_source()

            # Calculate profit
            profit = total_income - total_expenses

            # Current balances
            balances = {
                'btc_balance': self.btc_balance,
                'amazon_balance': self.amazon_balance,
                'amazon_currency': self.amazon_currency
            }

            return {
                'total_income': total_income,
                'total_expenses': total_expenses,
                'profit': profit,
                'income_by_source': income_by_source,
                'btc_balance': self.btc_balance,
                'amazon_balance': self.amazon_balance,
                'amazon_currency': self.amazon_currency
            }

        except Exception as e:
            self.logger.error(f"Error getting financial summary: {str(e)}")
            return {
                'total_income': 0.0,
                'total_expenses': 0.0,
                'profit': 0.0,
                'income_by_source': {},
                'btc_balance': self.btc_balance,
                'amazon_balance': self.amazon_balance,
                'amazon_currency': self.amazon_currency
            }