# app/managers/db_manager.py
"""
Database Manager for the Autonomous Income Generator.

This module handles database connections and queries.
"""
import logging
import time
from typing import Dict, Any, List, Optional, Union, Tuple
import mysql.connector
from mysql.connector import pooling
import json


class DatabaseManager:
    """
    Manages database connections and operations.
    """

    def __init__(self, host: str = "localhost", port: int = 3306, user: str = "root",
                 password: str = "", database: str = "income_generator", pool_size: int = 5):
        """
        Initialize the database manager.

        Args:
            host: Database host
            port: Database port
            user: Database user
            password: Database password
            database: Database name
            pool_size: Connection pool size
        """
        self.logger = logging.getLogger(__name__)
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.pool_size = pool_size

        # Create connection pool
        self._create_pool()

    def _create_pool(self) -> None:
        """
        Create a database connection pool.
        """
        try:
            self.pool = pooling.MySQLConnectionPool(
                pool_name="db_pool",
                pool_size=self.pool_size,
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database
            )

            self.logger.info(f"Created database connection pool for {self.database}")

            # Ensure the database exists and create it if it doesn't
            self._ensure_database_exists()

        except mysql.connector.Error as e:
            self.logger.error(f"Error creating database pool: {str(e)}")

            # If database doesn't exist, create it
            if e.errno == 1049:  # Unknown database
                self._create_database()
            else:
                raise

    def _ensure_database_exists(self) -> None:
        """
        Ensure the required database exists.
        """
        try:
            # Get a connection from the pool
            conn = self.pool.get_connection()

            # Check if the database exists
            cursor = conn.cursor()
            cursor.execute("SHOW DATABASES")
            databases = [db[0] for db in cursor.fetchall()]

            # If the database doesn't exist, create it
            if self.database not in databases:
                self._create_database()

            cursor.close()
            conn.close()

        except mysql.connector.Error as e:
            self.logger.error(f"Error checking database existence: {str(e)}")
            if e.errno == 1049:  # Unknown database
                self._create_database()
            else:
                raise

    def _create_database(self) -> None:
        """
        Create the database if it doesn't exist.
        """
        try:
            # Create a temporary connection without specifying a database
            conn = mysql.connector.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password
            )

            cursor = conn.cursor()

            # Create the database
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {self.database}")

            # Close the temporary connection
            cursor.close()
            conn.close()

            self.logger.info(f"Created database: {self.database}")

            # Recreate the connection pool with the new database
            self.pool = pooling.MySQLConnectionPool(
                pool_name="db_pool",
                pool_size=self.pool_size,
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database
            )

        except mysql.connector.Error as e:
            self.logger.error(f"Error creating database: {str(e)}")
            raise

    def _get_connection(self):
        """
        Get a connection from the pool.

        Returns:
            Database connection
        """
        try:
            return self.pool.get_connection()
        except mysql.connector.Error as e:
            self.logger.error(f"Error getting database connection: {str(e)}")
            raise

    def execute(self, query: str, params: tuple = None) -> int:
        """
        Execute a SQL query.

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            Row count or last insert ID
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(query, params or ())
            conn.commit()

            # Get row count or last insert ID
            if cursor.lastrowid:
                result = cursor.lastrowid
            else:
                result = cursor.rowcount

            cursor.close()
            return result

        except mysql.connector.Error as e:
            self.logger.error(f"Error executing query: {str(e)}")
            self.logger.error(f"Query: {query}")
            if params:
                self.logger.error(f"Params: {params}")
            raise

        finally:
            if conn:
                conn.close()

    def query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """
        Execute a query and fetch results.

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            List of dictionaries representing rows
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(dictionary=True)

            cursor.execute(query, params or ())
            result = cursor.fetchall()

            cursor.close()
            return result

        except mysql.connector.Error as e:
            self.logger.error(f"Error executing query: {str(e)}")
            self.logger.error(f"Query: {query}")
            if params:
                self.logger.error(f"Params: {params}")
            raise

        finally:
            if conn:
                conn.close()

    def query_one(self, query: str, params: tuple = None) -> Optional[Dict[str, Any]]:
        """
        Execute a query and fetch a single result.

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            Dictionary representing a row or None if no results
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(dictionary=True)

            cursor.execute(query, params or ())
            result = cursor.fetchone()

            cursor.close()
            return result

        except mysql.connector.Error as e:
            self.logger.error(f"Error executing query: {str(e)}")
            self.logger.error(f"Query: {query}")
            if params:
                self.logger.error(f"Params: {params}")
            raise

        finally:
            if conn:
                conn.close()

    def execute_many(self, query: str, params_list: List[tuple]) -> int:
        """
        Execute a query with multiple parameter sets.

        Args:
            query: SQL query
            params_list: List of parameter tuples

        Returns:
            Row count
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.executemany(query, params_list)
            conn.commit()

            result = cursor.rowcount

            cursor.close()
            return result

        except mysql.connector.Error as e:
            self.logger.error(f"Error executing query: {str(e)}")
            self.logger.error(f"Query: {query}")
            self.logger.error(f"Params list length: {len(params_list)}")
            raise

        finally:
            if conn:
                conn.close()

    def create_table(self, table_name: str, columns: Dict[str, str], primary_key: str,
                     foreign_keys: Dict[str, Tuple[str, str]] = None) -> bool:
        """
        Create a table if it doesn't exist.

        Args:
            table_name: Table name
            columns: Dictionary of column names and their definitions
            primary_key: Primary key column
            foreign_keys: Dictionary of foreign key columns and their references (table, column)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Build column definitions
            column_defs = [f"{name} {definition}" for name, definition in columns.items()]

            # Add primary key
            if primary_key:
                column_defs.append(f"PRIMARY KEY ({primary_key})")

            # Add foreign keys
            if foreign_keys:
                for fk_column, (ref_table, ref_column) in foreign_keys.items():
                    column_defs.append(
                        f"FOREIGN KEY ({fk_column}) REFERENCES {ref_table}({ref_column})"
                    )

            # Build the CREATE TABLE query
            query = f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(column_defs)})"

            # Execute the query
            self.execute(query)

            self.logger.info(f"Created table: {table_name}")
            return True

        except Exception as e:
            self.logger.error(f"Error creating table {table_name}: {str(e)}")
            return False

    def table_exists(self, table_name: str) -> bool:
        """
        Check if a table exists.

        Args:
            table_name: Table name

        Returns:
            True if the table exists, False otherwise
        """
        try:
            result = self.query(
                "SELECT COUNT(*) as count FROM information_schema.tables "
                "WHERE table_schema = %s AND table_name = %s",
                (self.database, table_name)
            )

            return result[0]['count'] > 0

        except Exception as e:
            self.logger.error(f"Error checking if table {table_name} exists: {str(e)}")
            return False

    def close(self) -> None:
        """
        Close the database connection pool.
        """
        try:
            # The MySQLConnectionPool doesn't have a close method,
            # but individual connections will be closed when returned to the pool
            self.logger.info("Database connections will be closed when returned to the pool")
        except Exception as e:
            self.logger.error(f"Error closing database connections: {str(e)}")