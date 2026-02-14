import sqlite3
from datetime import datetime
from typing import List, Tuple, Optional
from contextlib import contextmanager
import csv
import io

from config import DATABASE_NAME, DATE_FORMAT
from models import User, Order, Deadlines, Design

class Database:
    """Database handler for jersey bot"""
    
    def __init__(self, db_name: str = DATABASE_NAME):
        self.db_name = db_name
        self.init_database()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def init_database(self):
        """Initialize database tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Create users table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    vote_choice TEXT,
                    has_voted BOOLEAN DEFAULT 0,
                    has_ordered BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create orders table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER,
                    full_name TEXT NOT NULL,
                    shirt_number INTEGER NOT NULL,
                    shirt_name TEXT NOT NULL,
                    size TEXT NOT NULL,
                    receipt_file_id TEXT NOT NULL,
                    payment_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (telegram_id) REFERENCES users (telegram_id)
                )
            ''')
            
            # Create deadlines table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS deadlines (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    vote_deadline TIMESTAMP NOT NULL,
                    payment_deadline TIMESTAMP NOT NULL
                )
            ''')
            
            # Create designs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS designs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    image_file_id TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    display_order INTEGER DEFAULT 0
                )
            ''')
            
            # Insert default deadlines if table is empty
            cursor.execute('SELECT COUNT(*) FROM deadlines')
            if cursor.fetchone()[0] == 0:
                default_date = datetime.now().replace(year=datetime.now().year + 1)
                cursor.execute('''
                    INSERT INTO deadlines (id, vote_deadline, payment_deadline)
                    VALUES (1, ?, ?)
                ''', (default_date.strftime(DATE_FORMAT), default_date.strftime(DATE_FORMAT)))
    
    # User operations (keep existing)
    def get_user(self, telegram_id: int) -> Optional[User]:
        """Get user by telegram ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT telegram_id, vote_choice, has_voted, has_ordered 
                FROM users WHERE telegram_id = ?
            ''', (telegram_id,))
            row = cursor.fetchone()
            
            if row:
                return User(
                    telegram_id=row['telegram_id'],
                    vote_choice=row['vote_choice'],
                    has_voted=bool(row['has_voted']),
                    has_ordered=bool(row['has_ordered'])
                )
            return None
    
    def create_user(self, telegram_id: int):
        """Create new user"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO users (telegram_id, has_voted, has_ordered)
                VALUES (?, 0, 0)
            ''', (telegram_id,))
    
    def save_vote(self, telegram_id: int, design_id: int):
        """Save user's vote (now uses design_id)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users 
                SET vote_choice = ?, has_voted = 1
                WHERE telegram_id = ?
            ''', (str(design_id), telegram_id))
    
    def has_user_voted(self, telegram_id: int) -> bool:
        """Check if user has voted"""
        user = self.get_user(telegram_id)
        return user.has_voted if user else False
    
    def has_user_ordered(self, telegram_id: int) -> bool:
        """Check if user has ordered"""
        user = self.get_user(telegram_id)
        return user.has_ordered if user else False
    
    # Order operations (keep existing)
    def save_order(self, order: Order):
        """Save order to database"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Insert order
            cursor.execute('''
                INSERT INTO orders 
                (telegram_id, full_name, shirt_number, shirt_name, size, receipt_file_id, payment_time)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                order.telegram_id, order.full_name, order.shirt_number,
                order.shirt_name, order.size, order.receipt_file_id,
                order.payment_time.strftime(DATE_FORMAT)
            ))
            
            # Update user's has_ordered status
            cursor.execute('''
                UPDATE users SET has_ordered = 1
                WHERE telegram_id = ?
            ''', (order.telegram_id,))
    
    # Deadline operations (keep existing)
    def get_deadlines(self) -> Deadlines:
        """Get current deadlines"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT vote_deadline, payment_deadline FROM deadlines WHERE id = 1')
            row = cursor.fetchone()
            
            return Deadlines(
                vote_deadline=datetime.strptime(row['vote_deadline'], DATE_FORMAT),
                payment_deadline=datetime.strptime(row['payment_deadline'], DATE_FORMAT)
            )
    
    def set_vote_deadline(self, deadline: datetime):
        """Set new vote deadline"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE deadlines SET vote_deadline = ? WHERE id = 1
            ''', (deadline.strftime(DATE_FORMAT),))
    
    def set_payment_deadline(self, deadline: datetime):
        """Set new payment deadline"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE deadlines SET payment_deadline = ? WHERE id = 1
            ''', (deadline.strftime(DATE_FORMAT),))
    
    # NEW: Design operations
    def add_design(self, name: str, description: str, image_file_id: str, display_order: int = 0) -> int:
        """Add a new design"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO designs (name, description, image_file_id, display_order)
                VALUES (?, ?, ?, ?)
            ''', (name, description, image_file_id, display_order))
            return cursor.lastrowid
    
    def get_active_designs(self) -> List[Design]:
        """Get all active designs"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, name, description, image_file_id, created_at, is_active
                FROM designs 
                WHERE is_active = 1 
                ORDER BY display_order, created_at DESC
            ''')
            rows = cursor.fetchall()
            
            designs = []
            for row in rows:
                designs.append(Design(
                    id=row['id'],
                    name=row['name'],
                    description=row['description'] or '',
                    image_file_id=row['image_file_id'],
                    created_at=datetime.strptime(row['created_at'], '%Y-%m-%d %H:%M:%S'),
                    is_active=bool(row['is_active'])
                ))
            return designs
    
    def get_design(self, design_id: int) -> Optional[Design]:
        """Get design by ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, name, description, image_file_id, created_at, is_active
                FROM designs WHERE id = ?
            ''', (design_id,))
            row = cursor.fetchone()
            
            if row:
                return Design(
                    id=row['id'],
                    name=row['name'],
                    description=row['description'] or '',
                    image_file_id=row['image_file_id'],
                    created_at=datetime.strptime(row['created_at'], '%Y-%m-%d %H:%M:%S'),
                    is_active=bool(row['is_active'])
                )
            return None
    
    def update_design(self, design_id: int, name: str = None, description: str = None, 
                      image_file_id: str = None, is_active: bool = None):
        """Update design details"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            updates = []
            params = []
            
            if name is not None:
                updates.append("name = ?")
                params.append(name)
            if description is not None:
                updates.append("description = ?")
                params.append(description)
            if image_file_id is not None:
                updates.append("image_file_id = ?")
                params.append(image_file_id)
            if is_active is not None:
                updates.append("is_active = ?")
                params.append(1 if is_active else 0)
            
            if updates:
                params.append(design_id)
                cursor.execute(f'''
                    UPDATE designs 
                    SET {', '.join(updates)}
                    WHERE id = ?
                ''', params)
    
    def delete_design(self, design_id: int):
        """Soft delete a design"""
        self.update_design(design_id, is_active=False)
    
    # Statistics operations (updated)
    def get_vote_results(self) -> List[Tuple[str, int]]:
        """Get vote counts per design"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT d.name, COUNT(u.vote_choice) as count
                FROM designs d
                LEFT JOIN users u ON u.vote_choice = CAST(d.id AS TEXT) AND u.has_voted = 1
                WHERE d.is_active = 1
                GROUP BY d.id, d.name
                ORDER BY count DESC
            ''')
            return cursor.fetchall()
    
    def get_total_orders(self) -> int:
        """Get total number of orders"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM orders')
            return cursor.fetchone()[0]
    
    def export_orders_to_csv(self) -> str:
        """Export orders to CSV format"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT o.telegram_id, o.full_name, o.shirt_number, 
                       o.shirt_name, o.size, o.payment_time
                FROM orders o
                ORDER BY o.payment_time DESC
            ''')
            
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['Telegram ID', 'Full Name', 'Shirt Number', 
                           'Shirt Name', 'Size', 'Payment Time'])
            writer.writerows(cursor.fetchall())
            
            return output.getvalue()